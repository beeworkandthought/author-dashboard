import os
import json
import time as _time
import sqlite3

from flask import Flask, jsonify, request, send_from_directory, Response
from apscheduler.schedulers.background import BackgroundScheduler
from app import get_author_data, build_cards_json, AUTHORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
DB_PATH = os.path.join(DATA_DIR, 'lists.db')
CARDS_PATH = os.path.join(DATA_DIR, 'cards.json')

app = Flask(__name__, static_folder=BASE_DIR)


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = get_db()
    con.execute('''
        CREATE TABLE IF NOT EXISTS list_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            list_name   TEXT NOT NULL,
            author      TEXT,
            title       TEXT NOT NULL,
            summary     TEXT,
            url         TEXT,
            tag         TEXT,
            subtitle    TEXT,
            img_style   TEXT,
            item_type   TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    con.commit()
    con.close()


def refresh_cards():
    print('뉴스 업데이트 중...')
    try:
        authors_data = {a['name']: get_author_data(a) for a in AUTHORS}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CARDS_PATH, 'w', encoding='utf-8') as f:
            json.dump(build_cards_json(authors_data), f, ensure_ascii=False, indent=2)
        print('카드 업데이트 완료')
    except Exception as e:
        print(f'업데이트 실패: {e}')


def cards_stale():
    if not os.path.exists(CARDS_PATH):
        return True
    return (_time.time() - os.path.getmtime(CARDS_PATH)) > 23 * 3600


# ── Routes ─────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'sketch.html')


@app.route('/sw.js')
def sw():
    resp = Response(
        send_from_directory(BASE_DIR, 'sw.js').get_data(),
        mimetype='application/javascript'
    )
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp


@app.route('/manifest.json')
def manifest():
    return send_from_directory(BASE_DIR, 'manifest.json')


@app.route('/icon.svg')
def icon():
    return send_from_directory(BASE_DIR, 'icon.svg')


@app.route('/api/cards')
def api_cards():
    if cards_stale():
        refresh_cards()
    if not os.path.exists(CARDS_PATH):
        return jsonify([])
    with open(CARDS_PATH, encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/lists')
def api_lists():
    con = get_db()
    rows = con.execute('SELECT * FROM list_items ORDER BY created_at DESC').fetchall()
    con.close()
    result = {'digested': [], 'savor': []}
    for row in rows:
        d = dict(row)
        d['imgStyle'] = d.pop('img_style', None)
        d['type'] = d.pop('item_type', 'text')
        ln = d.get('list_name')
        if ln in result:
            result[ln].append(d)
    return jsonify(result)


@app.route('/api/lists/add', methods=['POST'])
def api_add():
    d = request.json
    con = get_db()
    cur = con.execute(
        '''INSERT INTO list_items
           (list_name, author, title, summary, url, tag, subtitle, img_style, item_type)
           VALUES (?,?,?,?,?,?,?,?,?)''',
        (d.get('list_name'), d.get('author'), d.get('title'), d.get('summary'),
         d.get('url'), d.get('tag'), d.get('subtitle'),
         d.get('imgStyle'), d.get('type'))
    )
    row_id = cur.lastrowid
    con.commit()
    con.close()
    return jsonify({'ok': True, 'id': row_id})


@app.route('/api/lists/remove', methods=['POST'])
def api_remove():
    con = get_db()
    con.execute('DELETE FROM list_items WHERE id = ?', (request.json['id'],))
    con.commit()
    con.close()
    return jsonify({'ok': True})


# ── Startup ─────────────────────────────────────────────

init_db()
if cards_stale():
    refresh_cards()

scheduler = BackgroundScheduler(timezone='Asia/Seoul')
scheduler.add_job(refresh_cards, 'cron', hour=9, minute=0)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
