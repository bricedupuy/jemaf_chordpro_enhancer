#!/usr/bin/env python3
"""
ChordPro to FreeShow Batch Processor - Enhanced Version with Online Support

This script can process ChordPro files from:
1. Local directory (original functionality)
2. Online JEMAF repository (new feature)

Features:
- Downloads files from https://jemaf.fr/ressources/chordPro/
- Uses online CSV metadata from GitHub
- Interactive song selection or batch processing
- Filename normalization (fixes jem917_0.chordpro -> jem917.chordpro)
- Default output directories
- Enhanced metadata with CSV data
- Deduplicated sections
- Generate FreeShow .show files
- French punctuation handling with non-breaking spaces

Usage: 
  python enhanced_chordpro_processor.py                    # Interactive online mode
  python enhanced_chordpro_processor.py --local <input_dir> [csv_file] [output_dir]
"""

import os
import sys
import csv
import json
import re
import hashlib
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict
import urllib.request
import urllib.parse
from urllib.error import URLError, HTTPError

@dataclass
class SongMetadata:
    """Song metadata from CSV file"""
    number: str
    title: str
    title2: str
    original_title: str
    composer: str
    author: str
    key: str
    format: str
    copyright: str
    reference: str
    theme: str
    tune_of: str
    volume: str
    supplement: str
    f1: str
    link: str

@dataclass
class ChordProSection:
    """Represents a section in a ChordPro file"""
    name: str  # e.g., "Strophe 1", "Refrain", "Pont"
    type: str  # verse, chorus, bridge, etc.
    number: Optional[str]
    content: List[str]
    raw_content: str

@dataclass
class FreeShowSlide:
    """Represents a slide in FreeShow format"""
    slide_id: str
    group: str
    color: str
    global_group: str
    lines: List[Dict]

class FrenchPunctuationHandler:
    """Handles French punctuation rules with non-breaking spaces"""
    
    # Non-breaking space character (Unicode U+00A0)
    NBSP = '\u00A0'
    
    # French double punctuation marks that require a non-breaking space
    DOUBLE_PUNCT_PATTERN = re.compile(r'\s*([;:!?»])')
    OPENING_GUILLEMETS_PATTERN = re.compile(r'(«)\s*')
    
    @classmethod
    def fix_french_punctuation(cls, text: str) -> str:
        """
        Fix French punctuation by replacing regular spaces with non-breaking spaces
        before double punctuation marks (;:!?») and after opening guillemets («).
        
        Args:
            text: Input text to process
            
        Returns:
            Text with proper French punctuation spacing
        """
        if not text or not isinstance(text, str):
            return text
        
        # Handle double punctuation: replace space before ;:!?Â» with non-breaking space
        text = cls.DOUBLE_PUNCT_PATTERN.sub(rf'{cls.NBSP}\1', text)
        
        # Handle opening guillemets: replace space after Â« with non-breaking space
        text = cls.OPENING_GUILLEMETS_PATTERN.sub(rf'\1{cls.NBSP}', text)
        
        return text

class OnlineResourceManager:
    """Manages online resource access for JEMAF ChordPro files"""
    
    JEMAF_BASE_URL = "https://jemaf.fr/ressources/chordPro/"
    CSV_URL = "https://raw.githubusercontent.com/bricedupuy/jemaf_chordpro_enhancer/refs/heads/main/custom-metadata.csv"
    
    @classmethod
    def get_available_files(cls) -> List[str]:
        """Get list of available ChordPro files from JEMAF website"""
        try:
            with urllib.request.urlopen(cls.JEMAF_BASE_URL) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
            
            # Find all links to .chordpro files using regex
            files = re.findall(r'href="([^"]+\.chordpro)"', html_content)
            
            # Sort numerically (handles both jem and jemk files)
            def extract_number(filename):
                # Handle both jem and jemk prefixes
                jem_match = re.search(r'jem(\d+)', filename)
                jemk_match = re.search(r'jemk(\d+)', filename)
                
                if jem_match:
                    return (0, int(jem_match.group(1)))  # jem files first
                elif jemk_match:
                    return (1, int(jemk_match.group(1)))  # jemk files second
                else:
                    return (2, 0)  # other files last
            
            files.sort(key=extract_number)
            return files
            
        except Exception as e:
            print(f"Error fetching file list: {e}")
            return []
    
    @classmethod
    def download_file(cls, filename: str, temp_dir: str) -> str:
        """Download a single ChordPro file to temporary directory"""
        url = cls.JEMAF_BASE_URL + filename
        
        # Normalize filename (fix issues like jem917_0.chordpro -> jem917.chordpro)
        normalized_filename = cls.normalize_filename(filename)
        local_path = os.path.join(temp_dir, normalized_filename)
        
        try:
            with urllib.request.urlopen(url) as response:
                content = response.read().decode('utf-8', errors='ignore')
            
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return local_path
            
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            return None
    
    @classmethod
    def normalize_filename(cls, filename: str) -> str:
        """
        Normalize filename to fix common issues
        Example: jem917_0.chordpro -> jem917.chordpro
        """
        # Remove _0 suffix before .chordpro
        filename = re.sub(r'_0\.chordpro$', '.chordpro', filename)
        
        # Ensure proper formatting: jem + number + .chordpro
        match = re.match(r'jem(\d+)', filename)
        if match:
            number = match.group(1)
            return f"jem{number.zfill(3)}.chordpro"
        
        return filename
    
    @classmethod
    def download_csv_metadata(cls, temp_dir: str) -> str:
        """Download CSV metadata file to temporary directory"""
        local_path = os.path.join(temp_dir, "custom-metadata.csv")
        
        try:
            with urllib.request.urlopen(cls.CSV_URL) as response:
                content = response.read().decode('utf-8', errors='ignore')
            
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return local_path
            
        except Exception as e:
            print(f"Error downloading CSV metadata: {e}")
            return None

class ChordProProcessor:
    def __init__(self, csv_file: str):
        """Initialize processor with metadata CSV file"""
        self.metadata = self.load_metadata(csv_file)
        self.chord_pattern = re.compile(r'\[([^\]]+)\]')
        
    def load_metadata(self, csv_file: str) -> Dict[str, SongMetadata]:
        """Load song metadata from CSV file"""
        metadata = {}
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Remove BOM if present
                if content.startswith('\ufeff'):
                    content = content[1:]
                
                reader = csv.DictReader(content.splitlines(), delimiter=';')
                for row in reader:
                    # Clean and strip whitespace from all fields
                    clean_row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
                    
                    fichier = clean_row.get('Fichier')
                    if not fichier:
                        continue
                        
                    # Use lowercase filename as lookup key for case-insensitive matching
                    key = fichier.lower()

                    metadata[key] = SongMetadata(
                        number=fichier,
                        title=clean_row.get('Titre', ''),
                        title2=clean_row.get('2e titre', ''),
                        original_title=clean_row.get('Titre original', ''),
                        composer=clean_row.get('Compositeur', ''),
                        author=clean_row.get('Auteur', ''),
                        key=clean_row.get('Tonalité', ''),
                        format=clean_row.get('Format', ''),
                        copyright=clean_row.get('Copyright', ''),
                        reference=clean_row.get('Référence', ''),
                        theme=clean_row.get('Thème', ''),
                        tune_of=clean_row.get('Air du', ''),
                        volume=clean_row.get('Vol.', ''),
                        supplement=clean_row.get('Suppl', ''),
                        f1=clean_row.get('F1', ''),
                        link=clean_row.get('Lien', '')
                    )
        except Exception as e:
            print(f"Error loading metadata from {csv_file}: {e}")
            
        return metadata
    
    def parse_chordpro_file(self, filepath: str) -> Tuple[Dict, List[ChordProSection]]:
        """Parse a ChordPro file and extract metadata and sections"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata = {}
        sections = []
        
        current_section_label = None
        current_section_content = []
        current_section_info = None
        in_section = False

        # Mappings for section types (case-insensitive)
        label_to_type_map = {
            'refrain': 'chorus',
            'chorus': 'chorus',
            'strophe': 'verse',
            'verse': 'verse',
            'pont': 'bridge',
            'bridge': 'bridge',
            'introduction': 'intro',
            'intro': 'intro',
            'fin': 'outro',
            'outro': 'outro',
        }

        lines = content.split('\n')
        for line in lines:
            stripped_line = line.strip()

            if stripped_line.startswith('{c:'):
                # This is a comment, potentially a section label
                current_section_label = stripped_line[3:-1].strip()
                if in_section:
                    current_section_content.append(line)

            elif stripped_line.startswith('{start_of_'):
                # End previous section if a new one starts without an end tag
                if in_section:
                    sections.append(ChordProSection(
                        name=current_section_info['name'],
                        type=current_section_info['type'],
                        number=current_section_info.get('number'),
                        content=current_section_content,
                        raw_content='\n'.join(current_section_content)
                    ))
                
                in_section = True
                block_type = stripped_line[10:-1].strip()  # e.g., 'verse'
                
                section_name = block_type.title()
                section_type = block_type
                section_number = None

                if current_section_label:
                    section_name = current_section_label
                    # Try to parse a standardized type and number from the label
                    label_lower = current_section_label.lower()
                    match = re.match(r'([a-zA-Z\s]+)\s*(\d+|[a-zA-Z])$', label_lower)
                    
                    type_part = label_lower
                    if match:
                        type_part = match.group(1).strip()
                        section_number = match.group(2)

                    # Find the standardized type
                    for key, value in label_to_type_map.items():
                        if key in type_part:
                            section_type = value
                            break
                    
                    current_section_label = None  # Consume the label
                
                current_section_info = {'name': section_name, 'type': section_type, 'number': section_number}
                current_section_content = []

            elif stripped_line.startswith('{end_of_'):
                if in_section:
                    sections.append(ChordProSection(
                        name=current_section_info['name'],
                        type=current_section_info['type'],
                        number=current_section_info.get('number'),
                        content=current_section_content,
                        raw_content='\n'.join(current_section_content)
                    ))
                    in_section = False
                    current_section_info = None
                    current_section_content = []
            
            elif stripped_line.startswith('{'):
                # It's a directive, parse and add to metadata
                directive_match = re.match(r'\{([^:]+)(?::(.*))?\}', stripped_line)
                if directive_match:
                    key = directive_match.group(1).strip()
                    value = directive_match.group(2).strip() if directive_match.group(2) else ''
                    metadata[key] = value
                if in_section:
                    current_section_content.append(line)
            
            elif in_section:
                current_section_content.append(line)

        return metadata, sections
    
    def deduplicate_sections(self, sections: List[ChordProSection]) -> Tuple[List[ChordProSection], List[int]]:
        """
        Deduplicate repeated sections and create a map of original to unique indices.
        
        Only considers actual lyrics/chords content, ignoring comments for deduplication.
        """
        unique_sections = []
        section_map = {}  # Maps content hash to index in unique_sections
        index_map = []  # Maps original section index to unique section index
        
        for section in sections:
            # Filter out comment lines for content comparison
            content_lines = [line for line in section.content if not line.strip().startswith('{c:')]
            content_hash = hashlib.md5('\n'.join(content_lines).encode('utf-8')).hexdigest()
            
            if content_hash in section_map:
                # This is a duplicate
                unique_index = section_map[content_hash]
                index_map.append(unique_index)
            else:
                # This is a new unique section
                unique_index = len(unique_sections)
                section_map[content_hash] = unique_index
                index_map.append(unique_index)
                unique_sections.append(section)
        
        return unique_sections, index_map
    
    def enhance_chordpro(self, filepath: str, output_dir: str) -> str:
        """Enhance a ChordPro file with metadata, deduplication, and French punctuation"""
        # Parse the original file
        file_metadata, sections = self.parse_chordpro_file(filepath)
        
        # Create a lookup key from the filename
        filename = Path(filepath).stem
        lookup_key = filename.lower()
        
        # Get enhanced metadata from CSV using the filename-based key
        csv_metadata = self.metadata.get(lookup_key)
        
        # Build enhanced ChordPro content
        output_lines = []
        
        # Add metadata headers
        if csv_metadata:
            output_lines.append(f"{{number: {csv_metadata.number}}}")
            # Fix French punctuation in title
            title = FrenchPunctuationHandler.fix_french_punctuation(csv_metadata.title)
            output_lines.append(f"{{title: {title}}}")
            
            if csv_metadata.author:
                author = FrenchPunctuationHandler.fix_french_punctuation(csv_metadata.author)
                output_lines.append(f"{{lyricist: {author}}}")
            if csv_metadata.composer:
                composer = FrenchPunctuationHandler.fix_french_punctuation(csv_metadata.composer)
                output_lines.append(f"{{composer: {composer}}}")
            if csv_metadata.copyright:
                copyright_text = FrenchPunctuationHandler.fix_french_punctuation(csv_metadata.copyright)
                output_lines.append(f"{{copyright: {copyright_text}}}")
                # Extract year from copyright
                year_match = re.search(r'(\d{4})', csv_metadata.copyright)
                if year_match:
                    output_lines.append(f"{{year: {year_match.group(1)}}}")
            
        # Add key from original file
        if 'key' in file_metadata:
            output_lines.append(f"{{key: {file_metadata['key']}}}")
        
        output_lines.append("")
        
        # Add all original sections with fixed French punctuation
        for section in sections:
            output_lines.append(f"{{start_of_{section.type}}}")
            for line in section.content:
                # Apply French punctuation fixes to content lines (but not directives)
                if not line.strip().startswith('{'):
                    line = FrenchPunctuationHandler.fix_french_punctuation(line)
                output_lines.append(line)
            output_lines.append(f"{{end_of_{section.type}}}")
            output_lines.append("")
        
        # Write enhanced file
        output_filename = f"{filename}-enhanced.chordpro"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        
        return output_path
    
    def parse_chord_line(self, line: str) -> Tuple[List[Dict], str]:
        """Parse a line with chords and return chord positions and clean text"""
        chords = []
        clean_text = line
        
        # Find all chord positions
        for match in self.chord_pattern.finditer(line):
            chord = match.group(1)
            pos = match.start()
            
            # Adjust position for previously removed chords
            adjusted_pos = pos
            for prev_chord in chords:
                if prev_chord['original_pos'] < pos:
                    adjusted_pos -= len(f"[{prev_chord['chord']}]")
            
            chords.append({
                'id': hashlib.md5(f"{chord}{pos}".encode('utf-8')).hexdigest()[:5],
                'pos': max(0, adjusted_pos),
                'key': chord,
                'chord': chord,
                'original_pos': pos
            })
        
        # Remove chord brackets from text
        clean_text = self.chord_pattern.sub('', line)
        
        return chords, clean_text
    
    def create_freeshow_slide(self, section: ChordProSection, slide_id: str, colors: Dict[str, str]) -> Dict:
        """Create a FreeShow slide from a ChordPro section"""
        
        # Determine slide colors and groups
        section_colors = {
            'verse': '',
            'chorus': '#f525d2',
            'bridge': '#f52598',
            'pre_chorus': '#25d2f5',
            'tag': '#f5d225',
            'intro': '',
            'outro': ''
        }
        
        global_groups = {
            'chorus': 'chorus',
            'bridge': 'bridge',
            'pre_chorus': 'pre_chorus'
        }
        
        slide_data = {
            "group": section.name,
            "color": section_colors.get(section.type, ''),
            "settings": {},
            "notes": "",
            "items": [{
                "lines": [],
                "style": "top:120px;left:50px;height:840px;width:1820px;",
                "align": "",
                "auto": False,
                "chords": {
                    "enabled": False
                }
            }]
        }
        
        # Add global group for chorus and bridge
        if section.type in global_groups:
            slide_data["globalGroup"] = global_groups[section.type]
        
        # Process each line in the section
        lines_data = []
        for line in section.content:
            if line.startswith('{c:'):
                continue  # Skip comment lines
            
            if line.strip():
                chords, clean_text = self.parse_chord_line(line)

                # Remove leading numbers like "1. " from the beginning of the line
                clean_text = re.sub(r'^\d+\.\s*', '', clean_text)
                
                # Apply French punctuation fixes to the display text
                clean_text = FrenchPunctuationHandler.fix_french_punctuation(clean_text)
                
                line_data = {
                    "align": "",
                    "text": [{
                        "value": clean_text,
                        "style": "font-size: 100px;"
                    }],
                    "chords": chords
                }
                lines_data.append(line_data)
        
        slide_data["items"][0]["lines"] = lines_data
        
        return slide_data
    
    def generate_freeshow_file(self, filepath: str, output_dir: str) -> str:
        """Generate a FreeShow .show file from enhanced ChordPro"""
        import time
        
        # Parse the enhanced file
        file_metadata, sections = self.parse_chordpro_file(filepath)
        
        # Extract song info
        filename = Path(filepath).stem
        song_number = file_metadata.get('number', '')
        title = file_metadata.get('title', filename)
        
        # Apply French punctuation fixes to title
        title = FrenchPunctuationHandler.fix_french_punctuation(title)
        
        # Generate unique IDs
        show_id = hashlib.md5(filename.encode('utf-8')).hexdigest()[:11]
        
        # Color scheme for different section types
        section_colors = {
            'verse': '',
            'chorus': '#f525d2', 
            'bridge': '#f52598'
        }
        
        # Deduplicate sections and build reference map
        unique_sections, index_map = self.deduplicate_sections(sections)
        
        # Create slides only for unique sections
        slides = {}
        unique_slide_ids = []
        for i, section in enumerate(unique_sections):
            slide_id = hashlib.md5(f"{section.type}{i}{section.raw_content}".encode('utf-8')).hexdigest()[:11]
            slides[slide_id] = self.create_freeshow_slide(section, slide_id, section_colors)
            unique_slide_ids.append(slide_id)

        # Create layout based on original song structure (with duplicates)
        layout_id = hashlib.md5(f"layout{filename}".encode('utf-8')).hexdigest()[:11]
        layout_slides = []
        
        for unique_index in index_map:
            slide_id = unique_slide_ids[unique_index]
            layout_slides.append({"id": slide_id})

        # Build the complete FreeShow data structure
        current_time = int(time.time() * 1000)  # Current timestamp in milliseconds
        
        # Apply French punctuation fixes to metadata
        author = FrenchPunctuationHandler.fix_french_punctuation(file_metadata.get('lyricist', ''))
        composer = FrenchPunctuationHandler.fix_french_punctuation(file_metadata.get('composer', ''))
        copyright_text = FrenchPunctuationHandler.fix_french_punctuation(file_metadata.get('copyright', ''))

        # Extract category from filename prefix
        category = "song"  # Default fallback
        if filename.startswith('jem'):
            if 'jemk' in filename.lower():
                category = "JEM Kids"
            else:
                category = "JEM"

        freeshow_data = [
            show_id,
            {
                "name": title,
                "origin": "jemaf",
                "private": False,
                "category": category,
                "settings": {
                    "activeLayout": layout_id,
                    "template":  None
                },
                
                "quickAccess": {
                    "number": song_number
                },
                "meta": {
                    "number": song_number,
                    "title": title,
                    "author": author,
                    "composer": composer,
                    "copyright": copyright_text,
                    "year": file_metadata.get('year', ''),
                    "key": file_metadata.get('key', '')
                },
                "slides": slides,
                "layouts": {
                    layout_id: {
                        "name": "Default",
                        "notes": "1 voix", 
                        "slides": layout_slides
                    }
                },
                "media": {}
            }
        ]
        
        # Write the .show file
        output_filename = f"{Path(filename).stem.replace('-enhanced','')}.show"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(freeshow_data, f, indent=4, ensure_ascii=False)
        
        return output_path

def interactive_song_selection(available_files: List[str], metadata: Dict[str, SongMetadata]) -> List[str]:
    """Interactive selection of songs to process"""
    print("\nAvailable songs:")
    print("=" * 80)
    
    # Display files with metadata when available
    for i, filename in enumerate(available_files, 1):
        base_name = OnlineResourceManager.normalize_filename(filename)
        lookup_key = Path(base_name).stem.lower()
        
        display_line = f"{i:3d}. {base_name}"
        
        if lookup_key in metadata:
            song_meta = metadata[lookup_key]
            if song_meta.title:
                display_line += f" - {song_meta.title}"
            if song_meta.author:
                display_line += f" ({song_meta.author})"
        
        print(display_line)
        
        # Add spacing every 10 items for readability
        if i % 10 == 0:
            print()
    
    print("\nOptions:")
    print("  Enter specific numbers (e.g., 1,5,10-15): Process selected songs")
    print("  Enter 'all': Process all songs")
    print("  Enter 'search <term>': Search for songs containing the term")
    print("  Enter 'quit' or 'q': Exit")
    
    while True:
        choice = input("\nYour choice: ").strip().lower()
        
        if choice in ['quit', 'q']:
            return []
        
        if choice == 'all':
            return available_files
        
        if choice.startswith('search '):
            search_term = choice[7:].strip().lower()
            matching_files = []
            
            print(f"\nSearching for '{search_term}':")
            for filename in available_files:
                base_name = OnlineResourceManager.normalize_filename(filename)
                lookup_key = Path(base_name).stem.lower()
                
                # Search in filename
                match_found = search_term in base_name.lower()
                
                # Search in metadata
                if lookup_key in metadata:
                    song_meta = metadata[lookup_key]
                    match_found = match_found or search_term in song_meta.title.lower()
                    match_found = match_found or search_term in song_meta.author.lower()
                
                if match_found:
                    matching_files.append(filename)
                    print(f"  {base_name}", end="")
                    if lookup_key in metadata and metadata[lookup_key].title:
                        print(f" - {metadata[lookup_key].title}")
                    else:
                        print()
            
            if not matching_files:
                print("  No matches found.")
                continue
            
            confirm = input(f"\nProcess these {len(matching_files)} matching songs? (y/n): ").strip().lower()
            if confirm == 'y':
                return matching_files
            continue
        
        # Parse number ranges and individual numbers
        try:
            selected_indices = set()
            
            for part in choice.split(','):
                part = part.strip()
                if '-' in part:
                    # Range like "10-15"
                    start, end = map(int, part.split('-'))
                    selected_indices.update(range(start - 1, end))  # Convert to 0-based
                else:
                    # Individual number
                    selected_indices.add(int(part) - 1)  # Convert to 0-based
            
            # Validate indices
            valid_indices = [i for i in selected_indices if 0 <= i < len(available_files)]
            if not valid_indices:
                print("No valid selections made.")
                continue
            
            selected_files = [available_files[i] for i in sorted(valid_indices)]
            return selected_files
            
        except (ValueError, IndexError) as e:
            print(f"Invalid selection format. Please try again.")
            continue

def main():
    """Main function to process files"""
    parser = argparse.ArgumentParser(
        description="ChordPro to FreeShow Processor with Online Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python script.py                                    # Interactive online mode
  python script.py --local /path/to/chordpro/files   # Local mode with default CSV
  python script.py --local /path/to/files metadata.csv /path/to/output
        """
    )
    
    parser.add_argument('--local', action='store_true', help='Use local files instead of online resources')
    parser.add_argument('input_dir', nargs='?', help='Input directory (local mode only)')
    parser.add_argument('csv_file', nargs='?', help='CSV metadata file (local mode only)')
    parser.add_argument('output_dir', nargs='?', help='Output directory (optional)')
    
    args = parser.parse_args()
    
    # Determine default output directories
    default_chordpro_output = "processedChordPro"
    default_freeshow_output = "processedFreeShow"
    
    if args.local:
        # Local mode - original functionality with enhancements
        if not args.input_dir:
            parser.error("Input directory is required for local mode")
        
        input_dir = args.input_dir
        csv_file = args.csv_file if args.csv_file else None
        output_dir = args.output_dir if args.output_dir else default_chordpro_output
        
        # Validate input parameters
        if not os.path.isdir(input_dir):
            print(f"Error: Input directory '{input_dir}' does not exist.")
            sys.exit(1)
        
        if csv_file and not os.path.isfile(csv_file):
            print(f"Error: CSV file '{csv_file}' does not exist.")
            sys.exit(1)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(default_freeshow_output, exist_ok=True)
        
        # Initialize processor
        if csv_file:
            processor = ChordProProcessor(csv_file)
        else:
            # Try to download online CSV as fallback
            print("No CSV file provided, attempting to download online metadata...")
            temp_dir = tempfile.mkdtemp()
            try:
                online_csv = OnlineResourceManager.download_csv_metadata(temp_dir)
                if online_csv:
                    processor = ChordProProcessor(online_csv)
                    print("Using online CSV metadata.")
                else:
                    print("Could not download online CSV, proceeding without enhanced metadata.")
                    # Create a dummy CSV for processing
                    dummy_csv = os.path.join(temp_dir, "dummy.csv")
                    with open(dummy_csv, 'w', encoding='utf-8') as f:
                        f.write("Fichier;Titre\n")  # Minimal header
                    processor = ChordProProcessor(dummy_csv)
            finally:
                # Don't clean up temp_dir here as processor might need the CSV
                pass
        
        # Process all .chordpro files in input directory
        chordpro_files = [f for f in os.listdir(input_dir) if f.endswith('.chordpro')]
        
        if not chordpro_files:
            print(f"No .chordpro files found in '{input_dir}'")
            sys.exit(0)
        
        print(f"Found {len(chordpro_files)} ChordPro files to process...")
        process_files_local(processor, input_dir, chordpro_files, output_dir, default_freeshow_output)
        
    else:
        # Online mode - new functionality
        print("ChordPro to FreeShow Processor - Online Mode")
        print("=" * 50)
        print("Fetching available songs from JEMAF repository...")
        
        # Create temporary directory for downloads
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Get available files
            available_files = OnlineResourceManager.get_available_files()
            if not available_files:
                print("Could not fetch file list from JEMAF repository.")
                sys.exit(1)
            
            print(f"Found {len(available_files)} songs available online.")
            
            # Download CSV metadata
            print("Downloading song metadata...")
            csv_file = OnlineResourceManager.download_csv_metadata(temp_dir)
            if not csv_file:
                print("Warning: Could not download metadata CSV. Proceeding without enhanced metadata.")
                # Create a dummy CSV
                csv_file = os.path.join(temp_dir, "dummy.csv")
                with open(csv_file, 'w', encoding='utf-8') as f:
                    f.write("Fichier;Titre\n")
            
            # Initialize processor
            processor = ChordProProcessor(csv_file)
            
            # Interactive song selection
            selected_files = interactive_song_selection(available_files, processor.metadata)
            
            if not selected_files:
                print("No files selected. Exiting.")
                sys.exit(0)
            
            # Create output directories
            chordpro_output_dir = args.output_dir if args.output_dir else default_chordpro_output
            freeshow_output_dir = default_freeshow_output
            
            os.makedirs(chordpro_output_dir, exist_ok=True)
            os.makedirs(freeshow_output_dir, exist_ok=True)
            
            # Process selected files
            process_files_online(processor, selected_files, temp_dir, chordpro_output_dir, freeshow_output_dir)
            
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

def process_files_local(processor: ChordProProcessor, input_dir: str, chordpro_files: List[str], 
                       chordpro_output_dir: str, freeshow_output_dir: str):
    """Process local ChordPro files"""
    processed_files = []
    
    print(f"Processing {len(chordpro_files)} local files...")
    
    for filename in chordpro_files:
        filepath = os.path.join(input_dir, filename)
        print(f"Processing: {filename}")
        
        try:
            # Enhance ChordPro file
            enhanced_path = processor.enhance_chordpro(filepath, chordpro_output_dir)
            print(f"  Enhanced: {os.path.basename(enhanced_path)}")
            
            # Generate FreeShow file
            show_path = processor.generate_freeshow_file(enhanced_path, freeshow_output_dir)
            print(f"  Show file: {os.path.basename(show_path)}")
            
            processed_files.append({
                'original': filepath,
                'enhanced': enhanced_path,
                'show': show_path
            })
            
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
    
    print(f"\nProcessed {len(processed_files)} files successfully!")
    print(f"Enhanced ChordPro files: {chordpro_output_dir}")
    print(f"FreeShow files: {freeshow_output_dir}")

def process_files_online(processor: ChordProProcessor, selected_files: List[str], temp_dir: str,
                        chordpro_output_dir: str, freeshow_output_dir: str):
    """Process online ChordPro files"""
    processed_files = []
    
    print(f"\nDownloading and processing {len(selected_files)} files...")
    
    for i, filename in enumerate(selected_files, 1):
        print(f"[{i}/{len(selected_files)}] Processing: {filename}")
        
        try:
            # Download file
            local_path = OnlineResourceManager.download_file(filename, temp_dir)
            if not local_path:
                print(f"  Error: Could not download {filename}")
                continue
            
            print(f"  Downloaded: {os.path.basename(local_path)}")
            
            # Enhance ChordPro file
            enhanced_path = processor.enhance_chordpro(local_path, chordpro_output_dir)
            print(f"  Enhanced: {os.path.basename(enhanced_path)}")
            
            # Generate FreeShow file
            show_path = processor.generate_freeshow_file(enhanced_path, freeshow_output_dir)
            print(f"  Show file: {os.path.basename(show_path)}")
            
            processed_files.append({
                'original': filename,
                'downloaded': local_path,
                'enhanced': enhanced_path,
                'show': show_path
            })
            
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
    
    print(f"\nProcessed {len(processed_files)} files successfully!")
    print(f"Enhanced ChordPro files: {chordpro_output_dir}")
    print(f"FreeShow files: {freeshow_output_dir}")
    
    # Display summary with song titles
    if processed_files:
        print(f"\nProcessed songs:")
        for file_info in processed_files:
            enhanced_path = file_info['enhanced']
            try:
                _, sections = processor.parse_chordpro_file(enhanced_path)
                with open(enhanced_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    title_match = re.search(r'\{title:\s*([^}]+)\}', content)
                    title = title_match.group(1) if title_match else "Unknown"
                    print(f"  {os.path.basename(file_info['enhanced']).replace('-enhanced.chordpro', '')} - {title}")
            except Exception:
                print(f"  {os.path.basename(file_info['enhanced'])}")

if __name__ == "__main__":
    main()
