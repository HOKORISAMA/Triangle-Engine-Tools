import sys
import struct
import argparse
import os
from typing import List, Optional

class Entry:
    def __init__(self, name: str, type: str, offset: int, size: int):
        self.name = name
        self.type = type
        self.offset = offset
        self.size = size

class CgfEntry(Entry):
    def __init__(self, name: str, type: str, offset: int, size: int, flags: int):
        super().__init__(name, type, offset, size)
        self.flags = flags

class ArcFile:
    def __init__(self, filename: str, entries: List[Entry]):
        self.filename = filename
        self.entries = entries

class CgfOpener:
    @staticmethod
    def try_open(filename: str) -> Optional[ArcFile]:
        with open(filename, 'rb') as file:
            count = struct.unpack('<I', file.read(4))[0]
            if not CgfOpener.is_sane_count(count):
                return None

            file.seek(0x14)
            offset1 = struct.unpack('<I', file.read(4))[0]
            file.seek(0x20)
            offset2 = struct.unpack('<I', file.read(4))[0]

            if 4 + count * 0x14 == (offset1 & ~0xC0000000):
                entry_size = 0x14
                next_offset = offset1
            elif 4 + count * 0x20 == (offset2 & ~0xC0000000):
                entry_size = 0x20
                next_offset = offset2
            else:
                return None

            index_size = entry_size * count
            file.seek(4)
            index_data = file.read(index_size)

            dir = []
            for i in range(count):
                name = index_data[i*entry_size:i*entry_size+entry_size-4].decode('utf-8').rstrip('\0')
                if not CgfOpener.is_valid_entry_name(name):
                    return None

                flags = next_offset >> 30
                offset = next_offset & ~0xC0000000

                if i + 1 == count:
                    file.seek(0, 2)  # Seek to end of file
                    next_offset = file.tell()
                else:
                    next_offset = struct.unpack('<I', index_data[(i+1)*entry_size+entry_size-4:(i+2)*entry_size])[0]

                size = (next_offset & ~0xC0000000) - offset

                if flags == 1 or name.lower().endswith('.iaf'):
                    entry = Entry(name, "image", offset, size)
                else:
                    entry = CgfEntry(name, "image", offset, size, flags)

                dir.append(entry)

            return ArcFile(filename, dir)

    @staticmethod
    def is_sane_count(count: int) -> bool:
        return 0 < count < 100000  # Arbitrary sanity check

    @staticmethod
    def is_valid_entry_name(name: str) -> bool:
        return name and not any(c in name for c in r'\/:*?"<>|')

def extract_file(arc_filename: str, entry: Entry, output_dir: str, output_name: str):
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_name)
    with open(arc_filename, 'rb') as arc, open(output_path, 'wb') as out:
        # Write 4 null bytes at the beginning
        out.write(b'\x00\x00\x00\x00')
        
        # Read the file content
        arc.seek(entry.offset)
        content = arc.read(entry.size)
        
        # Replace first 3 bytes with null bytes
        modified_content = b'\x00\x00\x00' + content[3:]
        
        # Write the modified content
        out.write(modified_content)
    
    print(f"Extracted and modified {entry.name} as {output_path}")

def main():
    parser = argparse.ArgumentParser(description="CGF Archive Opener")
    parser.add_argument("filename", help="Path to the CGF archive file")
    parser.add_argument("-l", "--list", action="store_true", help="List contents of the archive")
    parser.add_argument("-e", "--extract", nargs=2, metavar=('OUTPUT', 'INPUT'), help="Extract specific file from the archive")
    parser.add_argument("-a", "--all", action="store_true", help="Extract all files from the archive")
    parser.add_argument("-o", "--output", default=".", help="Specify output directory for extraction")
    args = parser.parse_args()

    arc_file = CgfOpener.try_open(args.filename)
    if not arc_file:
        print(f"Failed to open {args.filename}")
        return

    if args.list:
        print(f"Contents of {args.filename}:")
        for entry in arc_file.entries:
            print(f"{entry.name} ({entry.size} bytes)")

    if args.extract:
        output_name, input_name = args.extract
        for entry in arc_file.entries:
            if entry.name == input_name:
                extract_file(args.filename, entry, args.output, output_name)
                break
        else:
            print(f"File {input_name} not found in the archive")

    if args.all:
        for entry in arc_file.entries:
            extract_file(args.filename, entry, args.output, entry.name)

if __name__ == "__main__":
    main()
