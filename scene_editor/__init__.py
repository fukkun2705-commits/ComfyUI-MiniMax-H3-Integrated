"""ComfyUI H3 Scene Editor - local same-origin editor for H3SceneClipLoader scenes.json.
No node overrides or workflow changes. Requires ComfyUI PromptServer (aiohttp).
"""
import json
import os
import re
from pathlib import Path

import folder_paths
from aiohttp import web
from PIL import Image
from server import PromptServer

ROOT_NAME = 'H3_Scene_Projects'
WEB = Path(__file__).resolve().parent / 'web' / 'index.html'
PROJECT_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
MAX_IMAGE = 16 * 1024 * 1024
MAX_AUDIO = 60 * 1024 * 1024
MAX_VIDEO = 300 * 1024 * 1024


def root():
    p = (Path(folder_paths.get_input_directory()).resolve() / ROOT_NAME)
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def project_path(name):
    if not isinstance(name, str) or not PROJECT_RE.fullmatch(name):
        raise web.HTTPBadRequest(text='プロジェクト名は英数字・_・- のみ（64文字以内）です')
    base = root()
    p = (base / name).resolve()
    if not p.is_relative_to(base):
        raise web.HTTPBadRequest(text='不正なプロジェクトパス')
    return p


def safe_image_path(project, category, filename):
    if category not in ('characters', 'backgrounds', 'other', 'audio', 'video'):
        raise web.HTTPBadRequest(text='不正な画像カテゴリ')
    if not isinstance(filename, str) or not filename or '/' in filename or '\\' in filename or filename in ('.', '..'):
        raise web.HTTPBadRequest(text='不正なファイル名')
    base = project_path(project)
    target = (base / category / filename).resolve()
    if not target.is_relative_to(base):
        raise web.HTTPBadRequest(text='画像パスがプロジェクトの外です')
    return target


def new_scene():
    return {'version': 1, 'generation_mode': 'REF2VA', 'part': 1, 'clips': [
        {'clip': i, 'enabled': i == 1, 'duration': 6 if i == 1 else 2, 'prompt': '', 'references': [], 'ref_audios': [], 'ref_videos': []}
        for i in range(1, 8)]}


def validate_scene(data, project):
    if not isinstance(data, dict) or data.get('version') != 1 or data.get('generation_mode', 'REF2VA') not in ('REF2VA', 'T2VA', 'I2VA', 'FLF2VA'):
        raise web.HTTPBadRequest(text='version=1 / generation_mode は REF2VA / T2VA / I2VA / FLF2VA のいずれかです')
    if isinstance(data.get('part'), bool) or not isinstance(data.get('part'), int) or data['part'] < 1:
        raise web.HTTPBadRequest(text='partは1以上の整数です')
    clips = data.get('clips')
    if not isinstance(clips, list) or len(clips) != 7:
        raise web.HTTPBadRequest(text='Clip1～7の7項目が必要です')
    mode = data.get('generation_mode', 'REF2VA')
    normalized = []
    base = project_path(project)
    for i in range(1, 8):
        matches = [x for x in clips if isinstance(x, dict) and x.get('clip') == i]
        if len(matches) != 1:
            raise web.HTTPBadRequest(text=f'Clip{i}が重複または不足しています')
        c = matches[0]
        dur = c.get('duration')
        if isinstance(dur, bool) or not isinstance(dur, (int, float)) or not 0 < dur <= 15:
            raise web.HTTPBadRequest(text=f'Clip{i}: Durationは0より大きく15以下です')
        prompt = c.get('prompt')
        refs = c.get('references')
        if not isinstance(prompt, str) or len(prompt) > 50000:
            raise web.HTTPBadRequest(text=f'Clip{i}: プロンプトが不正です')
        if not isinstance(refs, list) or len(refs) > 9:
            raise web.HTTPBadRequest(text=f'Clip{i}: 参照画像は9枚までです')
        for ref in refs:
            if not isinstance(ref, str) or not ref.startswith(f'{ROOT_NAME}/{project}/'):
                raise web.HTTPBadRequest(text=f'Clip{i}: このプロジェクト内の画像を選択してください')
            path = (Path(folder_paths.get_input_directory()).resolve() / ref).resolve()
            if not path.is_relative_to(base) or not path.is_file() or path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
                raise web.HTTPBadRequest(text=f'Clip{i}: 参照画像が見つかりません: {ref}')
        audios = c.get('ref_audios', [])
        videos = c.get('ref_videos', [])
        if not isinstance(audios, list) or len(audios)>3 or not isinstance(videos,list) or len(videos)>3:
            raise web.HTTPBadRequest(text=f'Clip{i}: 音声最大3本、動画最大3本')
        for paths, category, suffixes in [(audios,'audio',('.wav','.flac','.mp3','.ogg','.m4a')), (videos,'video',('.mp4','.mov','.mkv','.webm'))]:
            for ref in paths:
                if not isinstance(ref,str) or not ref.startswith(f'{ROOT_NAME}/{project}/{category}/'):
                    raise web.HTTPBadRequest(text=f'Clip{i}: 参照メディアの場所が不正です')
                target = (Path(folder_paths.get_input_directory()).resolve()/ref).resolve()
                if not target.is_relative_to(base) or not target.is_file() or target.suffix.lower() not in suffixes:
                    raise web.HTTPBadRequest(text=f'Clip{i}: 参照メディアがありません: {ref}')
        enabled = c.get('enabled') is True
        if enabled and not prompt.strip():
            raise web.HTTPBadRequest(text=f'Clip{i}: 有効なClipにはプロンプトが必要です')
        if enabled and ((mode == 'REF2VA' and not 1 <= len(refs) <= 9) or (mode == 'T2VA' and bool(refs)) or (mode == 'FLF2VA' and len(refs) != 2) or (mode == 'I2VA' and len(refs) != 1)):
            raise web.HTTPBadRequest(text=f'Clip{i}: {mode} に合った参照画像数ではありません')
        if enabled and mode != 'REF2VA' and (audios or videos):
            raise web.HTTPBadRequest(text=f'Clip{i}: T2VA/I2VA/FLF2VA では参照Audio・Videoを指定しないでください')
        normalized.append({'clip': i, 'enabled': enabled, 'duration': dur, 'prompt': prompt, 'references': refs, 'ref_audios': audios, 'ref_videos': videos})
    return {'version': 1, 'generation_mode': mode, 'part': data['part'], 'clips': normalized}


def assert_same_origin(request):
    origin = request.headers.get('Origin')
    if origin:
        try:
            from urllib.parse import urlsplit
            o = urlsplit(origin)
            if o.netloc != request.host or o.scheme not in ('http', 'https'):
                raise web.HTTPForbidden(text='別サイトからの書き込みは許可されません')
        except ValueError:
            raise web.HTTPForbidden(text='不正なOrigin')
    if request.content_type not in ('application/json', 'multipart/form-data'):
        raise web.HTTPBadRequest(text='Content-Typeが不正です')


routes = PromptServer.instance.routes


@routes.get('/h3-scene-editor')
async def editor_page(request):
    return web.FileResponse(WEB, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@routes.get('/h3-scene-editor/api/projects')
async def projects(request):
    names = sorted([p.name for p in root().iterdir() if p.is_dir() and PROJECT_RE.fullmatch(p.name)])
    return web.json_response({'projects': names})


@routes.post('/h3-scene-editor/api/projects')
async def create_project(request):
    assert_same_origin(request)
    data = await request.json()
    name = data.get('name') if isinstance(data, dict) else None
    p = project_path(name)
    if p.exists():
        raise web.HTTPConflict(text='同名のプロジェクトが存在します')
    p.mkdir(parents=True)
    for category in ('characters', 'backgrounds', 'other', 'audio', 'video'):
        (p / category).mkdir()
    scene = new_scene()
    (p / 'scenes.json').write_text(json.dumps(scene, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return web.json_response({'project': name, 'scene': scene})


@routes.get('/h3-scene-editor/api/projects/{project}')
async def load_project(request):
    name = request.match_info['project']
    p = project_path(name)
    if not p.is_dir():
        raise web.HTTPNotFound(text='プロジェクトが存在しません')
    f = p / 'scenes.json'
    try:
        scene = json.loads(f.read_text(encoding='utf-8-sig')) if f.exists() else new_scene()
    except json.JSONDecodeError as exc:
        raise web.HTTPBadRequest(text=f'scenes.jsonの構文エラー: {exc}')
    imgs = []
    for category in ('characters', 'backgrounds', 'other', 'audio', 'video'):
        d = p / category
        if d.exists():
            for image in sorted(d.iterdir()):
                if image.is_file() and image.suffix.lower() in (('.png', '.jpg', '.jpeg', '.webp') if category in ('characters','backgrounds','other') else (('.wav','.flac','.mp3','.ogg','.m4a') if category=='audio' else ('.mp4','.mov','.mkv','.webm'))):
                    imgs.append({'category': category, 'name': image.name, 'path': f'{ROOT_NAME}/{name}/{category}/{image.name}', 'url': f'/h3-scene-editor/api/images/{name}/{category}/{image.name}'})
    return web.json_response({'project': name, 'scene': scene, 'images': [x for x in imgs if x['category'] in ('characters','backgrounds','other')], 'media': [x for x in imgs if x['category'] in ('audio','video')], 'scene_path': f'{ROOT_NAME}/{name}/scenes.json'})


@routes.post('/h3-scene-editor/api/projects/{project}/save')
async def save_project(request):
    assert_same_origin(request)
    name = request.match_info['project']
    p = project_path(name)
    if not p.is_dir():
        raise web.HTTPNotFound(text='プロジェクトが存在しません')
    data = await request.json()
    scene = validate_scene(data, name)
    dest = p / 'scenes.json'
    temp = p / 'scenes.json.tmp'
    temp.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, dest)
    return web.json_response({'ok': True, 'scene_path': f'{ROOT_NAME}/{name}/scenes.json'})


@routes.post('/h3-scene-editor/api/projects/{project}/upload')
async def upload_image(request):
    assert_same_origin(request)
    project = request.match_info['project']
    base = project_path(project)
    if not base.is_dir():
        raise web.HTTPNotFound(text='プロジェクトが存在しません')
    reader = await request.multipart()
    category = None
    payload = None
    filename = None
    async for part in reader:
        if part.name == 'category':
            category = (await part.text()).strip()
        elif part.name == 'file':
            filename = Path(part.filename or '').name
            if '/' in (part.filename or '') or '\\' in (part.filename or ''):
                raise web.HTTPBadRequest(text='不正なファイル名')
            payload = await part.read(decode=False)
            if len(payload) > MAX_IMAGE:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_IMAGE, actual_size=len(payload))
    if not filename or not payload or not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        raise web.HTTPBadRequest(text='PNG/JPG/WebP画像を選んでください')
    path = safe_image_path(project, category, filename)
    if path.exists():
        raise web.HTTPConflict(text='同名の画像が存在します（上書きしません）')
    from io import BytesIO
    try:
        with Image.open(BytesIO(payload)) as img:
            img.verify()
    except Exception:
        raise web.HTTPBadRequest(text='有効な画像ファイルではありません')
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(payload)
    return web.json_response({'ok': True, 'path': f'{ROOT_NAME}/{project}/{category}/{filename}'})


@routes.post('/h3-scene-editor/api/projects/{project}/upload-media')
async def upload_media(request):
    assert_same_origin(request)
    project=request.match_info['project']
    base=project_path(project)
    if not base.is_dir(): raise web.HTTPNotFound(text='プロジェクトが存在しません')
    reader=await request.multipart()
    category=None; data=None; filename=None
    async for part in reader:
        if part.name=='category': category=(await part.text()).strip()
        elif part.name=='file':
            filename=part.filename or ''
            if '/' in filename or '\\' in filename: raise web.HTTPBadRequest(text='ファイル名が不正です')
            data=await part.read(decode=False)
    if category not in ('audio','video') or not filename or data is None:
        raise web.HTTPBadRequest(text='音声または動画を指定してください')
    suffix=Path(filename).suffix.lower()
    extensions=('.wav','.flac','.mp3','.ogg','.m4a') if category=='audio' else ('.mp4','.mov','.mkv','.webm')
    limit=MAX_AUDIO if category=='audio' else MAX_VIDEO
    if suffix not in extensions or len(data)>limit or not data:
        raise web.HTTPBadRequest(text='形式またはファイルサイズが不正です')
    target=safe_media_path(project,category,filename)
    if target.exists(): raise web.HTTPConflict(text='同名ファイルがあります（上書きしません）')
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(data)
    return web.json_response({'ok':True,'path':f'{ROOT_NAME}/{project}/{category}/{filename}'})


def safe_media_path(project,category,filename):
    base=project_path(project)
    if category not in ('audio','video') or filename in ('.','..') or '/' in filename or '\\' in filename:
        raise web.HTTPBadRequest(text='メディアファイル名が不正です')
    path=(base/category/filename).resolve()
    if not path.is_relative_to(base): raise web.HTTPBadRequest(text='メディアパスが不正です')
    return path

@routes.get('/h3-scene-editor/api/images/{project}/{category}/{filename}')
async def preview_image(request):
    f = safe_image_path(request.match_info['project'], request.match_info['category'], request.match_info['filename'])
    if not f.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(f, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
