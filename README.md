# ChordPro to FreeShow Batch Processor

A Python script that processes ChordPro files to enhance them with metadata from CSV files and converts them to FreeShow presentation format. The script includes special handling for French typography with proper non-breaking spaces.

## Features

### 🎵 **ChordPro Enhancement**
- **Metadata Integration**: Automatically adds metadata from CSV files to ChordPro files
- **French Typography**: Proper non-breaking spaces before French double punctuation (`;`, `:`, `!`, `?`, `»`) and after opening guillemets (`«`)
- **Section Parsing**: Intelligent parsing of verses, choruses, bridges, and other song sections
- **UTF-8 Support**: Full Unicode support for international characters

### 🎬 **FreeShow Integration**
- **Slide Generation**: Creates FreeShow `.show` files with proper slide formatting
- **Section Deduplication**: Removes duplicate sections while maintaining song structure
- **Color Coding**: Automatic color coding for different section types
- **Chord Support**: Preserves chord information in FreeShow format

### 🔧 **Processing Features**
- **Batch Processing**: Processes entire directories of ChordPro files
- **Smart Deduplication**: Identifies and reuses identical song sections
- **Metadata Enrichment**: Combines file-based and CSV-based metadata
- **Error Handling**: Robust error handling with detailed reporting

## Requirements

### System Requirements
- Python 3.7 or higher
- UTF-8 capable text editor (recommended)

### Dependencies
No external dependencies required - uses only Python standard library modules:
- `os`, `sys`, `csv`, `json`, `re`, `hashlib`
- `pathlib`, `typing`, `dataclasses`, `collections`

## Installation

1. **Download the script**:
   ```bash
   wget https://your-script-location/chordpro_processor.py
   # or download manually
   ```

2. **Make it executable** (Linux/macOS):
   ```bash
   chmod +x chordpro_processor.py
   ```

3. **Verify Python version**:
   ```bash
   python3 --version  # Should be 3.7 or higher
   ```

## Usage

### Basic Usage

```bash
python3 chordpro_processor.py <input_dir> <csv_file> <output_dir>
```

### Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `input_dir` | Directory containing `.chordpro` files | `./songs/` |
| `csv_file` | CSV metadata file with song information | `./metadata.csv` |
| `output_dir` | Directory for output files | `./output/` |

### Example

```bash
python3 chordpro_processor.py ./input_songs/ ./song_metadata.csv ./processed_output/
```

This will:
1. Process all `.chordpro` files in `./input_songs/`
2. Use metadata from `./song_metadata.csv`
3. Create enhanced ChordPro and FreeShow files in `./processed_output/`

## Input File Formats

### ChordPro Files

Your ChordPro files should follow standard ChordPro format:

```chordpro
{title: Amazing Grace}
{key: G}

{start_of_verse}
[G]Amazing [C]grace, how [G]sweet the sound
That [D]saved a wretch like [G]me
{end_of_verse}

{start_of_chorus}
Was [G]blind but [C]now I [G]see
{end_of_chorus}
```

**Supported Section Types:**
- `verse` / `strophe`
- `chorus` / `refrain` 
- `bridge` / `pont`
- `intro` / `introduction`
- `outro` / `fin`

### CSV Metadata File

The CSV file should use semicolon (`;`) as delimiter and include these columns:

| Column | Description | Required |
|--------|-------------|----------|
| `Fichier` | Filename (without extension) | ✅ |
| `Titre` | Song title | ✅ |
| `2e titre` | Secondary title | ❌ |
| `Titre original` | Original title | ❌ |
| `Compositeur` | Composer name | ❌ |
| `Auteur` | Lyricist/Author | ❌ |
| `TonalitÃ©` | Musical key | ❌ |
| `Format` | Song format | ❌ |
| `Copyright` | Copyright information | ❌ |
| `RÃ©fÃ©rence` | Reference number | ❌ |
| `ThÃ¨me` | Theme/Category | ❌ |
| `Air du` | Tune reference | ❌ |
| `Vol.` | Volume number | ❌ |
| `Suppl` | Supplement info | ❌ |
| `F1` | Additional field | ❌ |
| `Lien` | Web link | ❌ |

**Example CSV:**
```csv
Fichier;Titre;Compositeur;Auteur;Copyright
001;Amazing Grace;Traditional;John Newton;Public Domain
002;How Great Thou Art;Stuart Hine;Stuart Hine;© 1953 Stuart Hine
```

## Output Files

### Enhanced ChordPro Files

The script creates enhanced ChordPro files with:
- **Metadata headers**: Added from CSV data
- **French typography**: Proper non-breaking spaces
- **Consistent formatting**: Standardized section markers

**Example output:**
```chordpro
{number: 001}
{title: Amazing Grace}
{lyricist: John Newton}
{composer: Traditional}
{copyright: Public Domain}
{key: G}

{start_of_verse}
[G]Amazing [C]grace, how [G]sweet the sound
That [D]saved a wretch like [G]me!
{end_of_verse}
```

### FreeShow Files

Creates `.show` files compatible with FreeShow presentation software:
- **Slide-based structure**: Each section becomes slides
- **Deduplication**: Reuses identical sections
- **Color coding**: Different colors for verses, choruses, bridges
- **Metadata preservation**: All song information included

## French Typography Features

### Automatic Punctuation Handling

The script automatically converts regular spaces to non-breaking spaces in the following cases:

| Before | After | Rule |
|--------|-------|------|
| `Bonjour ;` | `Bonjour ;` | Space before semicolon |
| `Qui es-tu ?` | `Qui es-tu ?` | Space before question mark |
| `Arrête !` | `Arrête !` | Space before exclamation |
| `Il dit :` | `Il dit :` | Space before colon |
| `« Bonjour` | `« Bonjour` | Space after opening guillemets |
| `au revoir »` | `au revoir »` | Space before closing guillemets |

**Note**: Non-breaking spaces (U+00A0) prevent awkward line breaks in the middle of punctuation.

## Advanced Configuration

### Section Type Mapping

The script automatically maps French and English section names:

| Input | Mapped Type | Color |
|-------|-------------|-------|
| `refrain`, `chorus` | `chorus` | Pink (#f525d2) |
| `strophe`, `verse` | `verse` | Default |
| `pont`, `bridge` | `bridge` | Pink variant (#f52598) |
| `introduction`, `intro` | `intro` | Default |
| `fin`, `outro` | `outro` | Default |

### Deduplication Logic

The script identifies duplicate sections by:
1. **Content comparison**: Ignoring comments and comparing only lyrics/chords
2. **Hash generation**: Creating MD5 hashes of normalized content
3. **Reference mapping**: Maintaining original song structure while reusing slides

## Troubleshooting

### Common Issues

**"No .chordpro files found"**
- Check that your input directory contains files with `.chordpro` extension
- Verify the directory path is correct

**"Error loading metadata from CSV"**
- Ensure CSV uses semicolon (`;`) as delimiter
- Check for proper UTF-8 encoding
- Verify required columns (`Fichier`) are present

**"Error processing [filename]"**
- Check ChordPro file syntax
- Ensure proper UTF-8 encoding
- Look for unmatched section tags

**Encoding Issues**
- Save all files as UTF-8
- Remove BOM (Byte Order Mark) if present
- Check for special characters in filenames

### Debug Mode

For debugging, you can add print statements or modify the script to show more detailed information:

```python
# Add this after line 200 for debugging
print(f"Loaded metadata for {len(self.metadata)} songs")
print(f"Processing sections: {[s.name for s in sections]}")
```

## File Structure Example

```
project/
├── chordpro_processor.py
├── input_songs/
│   ├── 001.chordpro
│   ├── 002.chordpro
│   └── 003.chordpro
├── song_metadata.csv
└── output/
    ├── 001-enhanced.chordpro
    ├── 001.show
    ├── 002-enhanced.chordpro
    ├── 002.show
    ├── 003-enhanced.chordpro
    └── 003.show
```

## License

This script is provided as-is for educational and practical use. Please ensure you have proper rights to the song content you're processing.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify input file formats match the specifications
3. Ensure all dependencies are properly installed
4. Check file permissions for input and output directories

## Version History

- **v1.0**: Initial release with basic ChordPro to FreeShow conversion
- **v2.0**: Added French punctuation handling and enhanced error reporting
- **Current**: Enhanced metadata processing and improved documentation
