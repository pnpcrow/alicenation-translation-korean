"""Local read-only IL2CPP method inspection using Il2CppDumper's script.json."""
import argparse
import json
from pathlib import Path
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from inventory import DEFAULT_GAME

parser = argparse.ArgumentParser()
parser.add_argument("method")
parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
parser.add_argument("--metadata", type=Path, default=Path("work/il2cpp/script.json"))
args = parser.parse_args()
meta = json.loads(args.metadata.read_text("utf-8"))
pe = pefile.PE(str(args.game / "GameAssembly.dll"), fast_load=True)
base = pe.OPTIONAL_HEADER.ImageBase
addresses = sorted(set(x["Address"] for x in meta["ScriptMethod"]))
names = {base + x["Address"]: x["Name"] for x in meta["ScriptMethod"]}
strings = {base + x["Address"]: x["Value"] for x in meta["ScriptString"]}
cs = Cs(CS_ARCH_X86, CS_MODE_64)
cs.detail = True
for method in meta["ScriptMethod"]:
    if args.method not in method["Name"]:
        continue
    addr = method["Address"]
    end = next((a for a in addresses if a > addr), addr + 256)
    print(method["Name"], hex(addr))
    for ins in cs.disasm(pe.get_data(addr, min(end - addr, 8192)), base + addr):
        note = ""
        for operand in ins.operands:
            if operand.type == 2:
                note = names.get(operand.imm, "")
            elif operand.type == 3 and ins.reg_name(operand.mem.base) == "rip":
                ptr = ins.address + ins.size + operand.mem.disp
                if ptr in strings:
                    note = repr(strings[ptr])
        print(f"{ins.address-base:08x} {ins.mnemonic:8} {ins.op_str:48} {note}")
