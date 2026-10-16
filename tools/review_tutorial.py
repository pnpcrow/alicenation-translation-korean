"""Create an analysis-only comparison of the generated tutorial art at imported size."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
rows=[r for r in json.loads((ROOT/'assets/images/tutorial/manifest.json').read_text('utf-8')) if r['status']=='translated']
out=ROOT/'work/tutorial-review'
out.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',16)
for start in range(0,len(rows),8):
    sheet=Image.new('RGB',(1280,1320),'#c9c9c9')
    draw=ImageDraw.Draw(sheet)
    for i,row in enumerate(rows[start:start+8]):
        x,y=(i%2)*640,(i//2)*330
        before=Image.open(ROOT/'reference/tutorial-sprites'/ (row['name']+'.png')).convert('RGB')
        after=Image.open(ROOT/'assets/images/tutorial'/row['file']).convert('RGB').resize((300,300),Image.Resampling.LANCZOS)
        sheet.paste(before,(x,y))
        sheet.paste(after,(x+310,y))
        draw.text((x+4,y+305),row['name']+' : original / Korean 300px',fill='black',font=font)
    sheet.save(out/f'{start//8:02}.png')
print(len(rows),'images in',out)
