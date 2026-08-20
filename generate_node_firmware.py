import os
import shutil
import subprocess

# List of nodes you want firmware for
nodes = ["RTU1", "BCU1", "BCU2", "RELAY1", "RELAY2", "RELAY3", "METER1", "METER2"]

# Paths to the source templates
BASE_SRC = os.path.join("firmware", "main_baseline.c")
TAMPER_SRC = os.path.join("firmware", "main_tampered.c")

# Where to put the generated .elf files (they will also be in firmware/)
FIRMWARE_DIR = "firmware"

# We'll use the existing build.sh to compile, but we need to modify the source temporarily.
# Instead, we copy the source, replace the NODE string, then compile with gcc directly.

def compile_firmware(src_file, elf_output):
    """Compile a single .c file with arm-none-eabi-gcc to an elf."""
    cmd = [
        "arm-none-eabi-gcc",
        "-mcpu=cortex-m3",
        "-mthumb",
        "-nostdlib",
        "-T", os.path.join(FIRMWARE_DIR, "linker.ld"),
        "-o", elf_output,
        src_file,
        os.path.join(FIRMWARE_DIR, "startup.c"),
        "-Wl,--gc-sections",
    ]
    subprocess.run(cmd, check=True, capture_output=True)

for node in nodes:
    # ----- Baseline -----
    node_baseline_src = os.path.join(FIRMWARE_DIR, f"{node}_baseline.c")
    # Copy template and replace the NODE string
    with open(BASE_SRC, "r") as f:
        content = f.read()
    content = content.replace('"RELAY-02"', f'"{node}"')  # adjust if needed
    with open(node_baseline_src, "w") as f:
        f.write(content)
    # Compile
    elf_out = os.path.join(FIRMWARE_DIR, f"{node}_baseline.elf")
    compile_firmware(node_baseline_src, elf_out)
    print(f"Compiled {node}_baseline.elf")

    # ----- Tampered -----
    node_tamper_src = os.path.join(FIRMWARE_DIR, f"{node}_tampered.c")
    with open(TAMPER_SRC, "r") as f:
        content = f.read()
    content = content.replace('"RELAY-02"', f'"{node}"')
    with open(node_tamper_src, "w") as f:
        f.write(content)
    elf_out = os.path.join(FIRMWARE_DIR, f"{node}_tampered.elf")
    compile_firmware(node_tamper_src, elf_out)
    print(f"Compiled {node}_tampered.elf")

print("All firmwares generated.")