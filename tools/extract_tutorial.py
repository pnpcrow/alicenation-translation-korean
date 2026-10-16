"""Export tutorial atlas sprites and their original packing metadata for review."""
from pathlib import Path
import json
import UnityPy
from PIL import Image, ImageDraw, ImageFont
from UnityPy.export.SpriteHelper import SpriteSettings
from inventory import DEFAULT_GAME

ROOT = Path(__file__).resolve().parents[1]


def main():
    index = json.loads((ROOT / 'work/analysis/objects.json').read_text('utf-8'))
    rel, = {r['source'] for r in index if 'teachatlas.spriteatlas_' in r['source']}
    env = UnityPy.load(str(DEFAULT_GAME / rel))
    atlas, = [o.read() for o in env.objects if o.type.name == 'SpriteAtlas']
    out = ROOT / 'reference/tutorial-sprites'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for obj in env.objects:
        if obj.type.name != 'Sprite':
            continue
        sprite = obj.read()
        packed = next(v for k, v in atlas.m_RenderDataMap if k == sprite.m_RenderDataKey)
        settings = SpriteSettings(packed.settingsRaw)
        im = sprite.image.convert('RGBA')
        im.save(out / (sprite.m_Name + '.png'))
        rect = packed.textureRect
        rows.append({'name':sprite.m_Name, 'path_id':obj.path_id, 'source':rel,
                     'texture_id':packed.texture.path_id, 'rect':[rect.x,rect.y,rect.width,rect.height],
                     'settings_raw':packed.settingsRaw, 'rotation':int(settings.packingRotation),
                     'packing_mode':int(settings.packingMode), 'image_size':list(im.size)})
    rows.sort(key=lambda r:r['name'])
    (out / 'index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n','utf-8')
    font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 16)
    for start in range(0,len(rows),16):
        sheet = Image.new('RGB',(1600,1200),'#c9c9c9')
        draw = ImageDraw.Draw(sheet)
        for i,row in enumerate(rows[start:start+16]):
            x,y=(i%4)*400,(i//4)*300
            im=Image.open(out/(row['name']+'.png')).convert('RGBA')
            im.thumbnail((390,265))
            sheet.paste(im,(x+(400-im.width)//2,y),im)
            draw.text((x+5,y+272),row['name']+' '+str(row['image_size']),font=font,fill='black')
        sheet.save(out/f'sheet-{start//16:02}.jpg',quality=95)
    print(f'Exported {len(rows)} tutorial sprites')
    print('Packing modes:',sorted({r['packing_mode'] for r in rows}))
    print('Rotations:',sorted({r['rotation'] for r in rows}))


if __name__ == '__main__':
    main()
