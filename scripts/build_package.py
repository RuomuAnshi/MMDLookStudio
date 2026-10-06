"""Create the installable extension without filesystem metadata or bytecode."""
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
source = ROOT/'zelda_preset'
manifest = tomllib.loads((source/'blender_manifest.toml').read_text())
target = ROOT/'output'/f'zelda_daylight-{manifest["version"]}.zip'
target.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as package:
    for file in sorted(source.iterdir()):
        if file.is_file() and not file.name.startswith('._') and file.suffix != '.pyc':
            package.write(file,file.name)
    package.write(ROOT/'README.md','README.md')
with zipfile.ZipFile(target) as package:
    assert package.testzip() is None
print(target)
