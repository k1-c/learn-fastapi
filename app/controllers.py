from fastapi import FastAPI, Depends, HTTPException  # new
from fastapi.security import HTTPBasic, HTTPBasicCredentials  # new

from starlette.templating import Jinja2Templates
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED  # new

import db
from models import User, Task

import hashlib
import re

from mycalendar import MyCalendar
from datetime import datetime, timedelta


pattern = re.compile(r'\w{4,20}')  # 任意の4~20の英数字を示す正規表現
pattern_pw = re.compile(r'\w{6,20}')  # 任意の6~20の英数字を示す正規表現
pattern_mail = re.compile(r'^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$')  # e-mailの正規表現


app = FastAPI(
    title="FastAPIでつくるtoDoアプリケーション",
    description="FastAPIチュートリアル：FastAPI(とstarlette)でシンプルなtoDoアプリを作りましょう．",
    version="0.9 beta",
)

security = HTTPBasic()

# new テンプレート関連の設定 (jinja2)
templates = Jinja2Templates(directory="app/templates")
jinja_env = templates.env  # Jinja2.Environment : filterやglobalの設定用


def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    # Basic認証で受け取った情報
    username = credentials.username
    password = hashlib.md5(credentials.password.encode()).hexdigest()

    """ [new] 今日の日付と来週の日付"""
    today = datetime.now()
    next_w = today + timedelta(days=7)  # １週間後の日付

    # データベースからユーザ名が一致するデータを取得
    user = db.session.query(User).filter(User.username == username).first()
    db.session.close()

    # 該当ユーザがいない場合
    if user is None or user.password != password:
        error = 'ユーザ名かパスワードが間違っています．'
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Basic"},
        )

    task = db.session.query(Task).filter(Task.user_id == user.id).all()
    db.session.close()

    """ [new] カレンダー関連 """
    # カレンダーをHTML形式で取得
    cal = MyCalendar(username,
                     {t.deadline.strftime('%Y%m%d'): t.done for t in task})  # 予定がある日付をキーとして渡す

    cal = cal.formatyear(today.year, 4)  # カレンダーをHTMLで取得

    # 直近のタスクだけでいいので、リストを書き換える
    task = [t for t in task if today <= t.deadline <= next_w]
    links = [t.deadline.strftime('/todo/' + username + '/%Y/%m/%d') for t in task]  # 直近の予定リンク

    return templates.TemplateResponse('admin.html',
                                      {'request': request,
                                       'user': user,
                                       'task': task,
                                       'links': links,
                                       'calender': cal})


async def register(request: Request):
    if request.method == "GET":
        return templates.TemplateResponse(
            "register.html", {"request": request, "username": "", "error": []}
        )

    if request.method == "POST":
        # POSTデータ
        data = await request.form()
        username = data.get('username')
        password = data.get('password')
        password_tmp = data.get('password_tmp')
        mail = data.get('mail')

        error = []

        tmp_user = db.session.query(User).filter(User.username == username).first()

        # 怒涛のエラー処理
        if tmp_user is not None:
            error.append('同じユーザ名のユーザが存在します。')
        if password != password_tmp:
            error.append('入力したパスワードが一致しません。')
        if pattern.match(username) is None:
            error.append('ユーザ名は4~20文字の半角英数字にしてください。')
        if pattern_pw.match(password) is None:
            error.append('パスワードは6~20文字の半角英数字にしてください。')
        if pattern_mail.match(mail) is None:
            error.append('正しくメールアドレスを入力してください。')

        # エラーがあれば登録ページへ戻す
        if error:
            return templates.TemplateResponse('register.html',
                                              {'request': request,
                                               'username': username,
                                               'error': error})

        # 問題がなければユーザー登録
        user = User(username, password, mail)
        db.session.add(user)
        db.session.commit()
        db.session.close()

        return templates.TemplateResponse('complete.html',
                                          {'request': request,
                                           'username': username})
