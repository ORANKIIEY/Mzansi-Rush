import json

with open("data/mzansi_asphalt.json") as f:
    data = json.load(f)

for y, row in enumerate(data["grid"]):
    print(f"{y:2d} " + row.replace("G", ".").replace("W", "#"))
