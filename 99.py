import discord
from discord.ext import commands
import asyncio
import os
import re
import time
import json
import requests
from datetime import datetime
from typing import Dict, Any

# Nhập dữ liệu khi khởi chạy
TOKEN = input("Nhập Token Bot: ")
IDADMIN_GOC = int(input("Nhập ID Admin gốc: "))
PREFIX = input("Nhập Prefix Bot: ")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# RAM lưu trạng thái
admins = [IDADMIN_GOC]
saved_files = {}
running_tasks = {}

# Lưu thông tin task
task_info = {}

# Lệnh addadmin
@bot.command()
async def addadmin(ctx, member: discord.Member):
    if ctx.author.id != IDADMIN_GOC:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    if member.id not in admins:
        admins.append(member.id)
        await ctx.send(f"Đã thêm `{member.name}` vào danh sách admin.")
    else:
        await ctx.send("Người này đã là admin rồi.")

# Lệnh deladmin
@bot.command()
async def deladmin(ctx, member: discord.Member):
    if ctx.author.id != IDADMIN_GOC:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    if member.id in admins and member.id != IDADMIN_GOC:
        admins.remove(member.id)
        await ctx.send(f"Đã xoá `{member.name}` khỏi danh sách admin.")
        
        # Dừng tất cả các task do admin này tạo
        to_remove = [task_id for task_id, info in task_info.items() if info['admin_id'] == member.id]
        for task_id in to_remove:
            if task_id in running_tasks:
                running_tasks[task_id].cancel()  # Dừng task
                del running_tasks[task_id]
            del task_info[task_id]
        await ctx.send(f"Đã dừng tất cả các task do `{member.name}` tạo.")
    else:
        await ctx.send("Không thể xoá admin gốc hoặc người này không phải admin.")

@bot.command()
async def listadmin(ctx):
    msg = "**Danh sách admin hiện tại:**\n"
    for admin_id in admins:
        try:
            user = await bot.fetch_user(admin_id)
            if admin_id == IDADMIN_GOC:
                msg += f"- `{user.name}` (Admin Gốc)\n"
            else:
                msg += f"- `{user.name}`\n"
        except Exception as e:
            msg += f"- `{admin_id}` (Không tìm được tên)\n"
    await ctx.send(msg)

# Lưu file
@bot.command()
async def setngonmess(ctx):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền.")
    if not ctx.message.attachments:
        return await ctx.send("Vui lòng đính kèm file.")
    admin_id = str(ctx.author.id)
    file = ctx.message.attachments[0]
    filename = file.filename
    os.makedirs(f"data/{admin_id}", exist_ok=True)
    path = f"data/{admin_id}/{filename}"
    await file.save(path)
    await ctx.send(f"Đã lưu file `{filename}` vào thư mục của bạn.")

# Xem các file đã lưu
@bot.command()
async def xemngonmess(ctx):
    admin_id = str(ctx.author.id)
    folder = f"data/{admin_id}"
    if not os.path.exists(folder):
        return await ctx.send("Bạn chưa lưu file nào.")
    files = os.listdir(folder)
    if not files:
        return await ctx.send("Bạn chưa lưu file nào.")
    msg = f"**Danh sách file của `{ctx.author.name}`:**\n"
    for fname in files:
        path = os.path.join(folder, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                preview = f.read(100).replace('\n', ' ')
                msg += f"`{fname}`: {preview}...\n"
        except:
            msg += f"`{fname}`: (Không đọc được nội dung)\n"
    await ctx.send(msg)


def get_uid(cookie):
    try:
        return re.search('c_user=(\\d+)', cookie).group(1)
    except:
        return '0'

def get_fb_dtsg_jazoest(cookie, target_id):
    try:
        response = requests.get(
            f'https://mbasic.facebook.com/privacy/touch/block/confirm/?bid={target_id}&ret_cancel&source=profile',
            headers={'cookie': cookie, 'user-agent': 'Mozilla/5.0'})
        fb_dtsg = re.search('name="fb_dtsg" value="([^"]+)"', response.text).group(1)
        jazoest = re.search('name="jazoest" value="([^"]+)"', response.text).group(1)
        return fb_dtsg, jazoest
    except:
        return None, None

def send_message(idcanspam, fb_dtsg, jazoest, cookie, message_body):
    try:
        uid = get_uid(cookie)
        timestamp = int(time.time() * 1000)
        data = {
            'thread_fbid': idcanspam,
            'action_type': 'ma-type:user-generated-message',
            'body': message_body,
            'client': 'mercury',
            'author': f'fbid:{uid}',
            'timestamp': timestamp,
            'source': 'source:chat:web',
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'ephemeral_ttl_mode': '',
            '__user': uid,
            '__a': '1',
            '__req': '1b',
            '__rev': '1015919737',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest
        }
        headers = {
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/messages/t/{idcanspam}'
        }
        response = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers)
        return response.status_code == 200
    except:
        return False

# Gửi loop
async def spam_loop(ctx, idgroup, cookie, filename, delay, admin_id):
    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, idgroup)
    if not fb_dtsg:
        await ctx.send("Cookie không hợp lệ.")
        return
    path = saved_files.get(filename)
    if not path:
        await ctx.send("Không tìm thấy file.")
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    start_time = time.time()
    task_info[idgroup] = {'admin_id': admin_id, 'start_time': start_time, 'task_count': 0}
    
    print(f"[+] Bắt đầu spam vào nhóm {idgroup}...")
    await ctx.send(f"Bắt đầu gửi tin nhắn đến nhóm `{idgroup}`...")
    
    while idgroup in running_tasks:
        success = send_message(idgroup, fb_dtsg, jazoest, cookie, content)
        if success:
            print(f"[+] Đã gửi 1 tin nhắn vào nhóm {idgroup}")
        else:
            print(f"[!] Gửi thất bại vào nhóm {idgroup}")
        await asyncio.sleep(float(delay))

@bot.command()
async def ngonmess(ctx, id_box: str, cookie: str, filename: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    admin_id = str(ctx.author.id)
    file_path = f"data/{admin_id}/{filename}"

    if not os.path.exists(file_path):
        return await ctx.send(f"File `{filename}` không tồn tại trong thư mục của bạn.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(file_path, 'r', encoding='utf-8') as f:
        message_body = f.read().strip()

    print(f"[+] Đã bắt đầu spam box {id_box} với file {filename} (delay: {speed}s)")
    await ctx.send(f"**[INFO]** Bắt đầu spam box `{id_box}` với file `{filename}` mỗi `{speed}` giây.")

    task_id = f"ngonmess_{id_box}_{time.time()}"
    async def spam_loop_task():
        while True:
            success = send_message(id_box, fb_dtsg, jazoest, cookie, message_body)
            if success:
                print(f"[+] Đã gửi 1 tin nhắn vào box {id_box}")
            else:
                print(f"[!] Gửi thất bại vào box {id_box}")
            await asyncio.sleep(speed)

    task = asyncio.create_task(spam_loop_task())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"Đã bắt đầu spam vào box `{id_box}` với file `{filename}`.")
    
# Lệnh stopngonmess dừng tất cả task theo idgroup
@bot.command()
async def stopngonmess(ctx, idgroup):
    # Kiểm tra tất cả task liên quan đến idgroup
    tasks_to_stop = [task_id for task_id in running_tasks if task_id.startswith(f"ngonmess_{idgroup}")]

    if not tasks_to_stop:
        return await ctx.send(f"Không có task nào đang chạy cho nhóm `{idgroup}`.")
    
    # Dừng tất cả task liên quan đến idgroup này
    for task_id in tasks_to_stop:
        if task_info.get(task_id, {}).get('admin_id') == ctx.author.id:
            running_tasks[task_id].cancel()  # Dừng task
            del running_tasks[task_id]
            del task_info[task_id]
            await ctx.send(f"Đã dừng task cho lệnh ngonmess: `{idgroup}`.")
        else:
            await ctx.send(f"Bạn không có quyền dừng task `{task_id}`.")

# Lệnh tabngonmess
@bot.command()
async def tabngonmess(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("ngonmess_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task ngonmess nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("ngonmess_"):
                group_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Group ID: {group_id} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task ngonmess nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")

@bot.command()
async def nhay(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt` trong thư mục data.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    task_id = f"nhay_{id_box}_{time.time()}"
    
    async def loop_nhay():
        index = 0
        while True:
            send_message(id_box, fb_dtsg, jazoest, cookie, lines[index])
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_nhay())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"Đã bắt đầu nhảy tin nhắn vào box `{id_box}` với tốc độ `{speed}` giây.")
    
@bot.command()
async def stopnhay(ctx, id_box: str):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    tasks_to_stop = [task_id for task_id in running_tasks if task_id.startswith(f"nhay_{id_box}")]

    if not tasks_to_stop:
        return await ctx.send(f"Không có tác vụ nào đang chạy cho box `{id_box}`.")
    
    # Dừng tất cả task liên quan đến id_box này
    for task_id in tasks_to_stop:
        if task_info.get(task_id, {}).get('admin_id') == ctx.author.id:
            running_tasks[task_id].cancel()  # Dừng task
            del running_tasks[task_id]
            del task_info[task_id]
            await ctx.send(f"Đã dừng task `{task_id}` gửi tin nhắn vào box `{id_box}`.")
        else:
            await ctx.send(f"Bạn không có quyền dừng task `{task_id}`.")
        
@bot.command()
async def reo(ctx, id_box: str, cookie: str, delay: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    # Kiểm tra file nhay.txt
    file_path = "nhay.txt"
    if not os.path.exists(file_path):
        return await ctx.send("File `nhay.txt` không tồn tại.")

    # Yêu cầu nhập ID người cần tag
    await ctx.send("Vui lòng nhập ID người cần tag:")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        tagged_id = msg.content.strip()
        if not tagged_id.isdigit():
            return await ctx.send("ID tag phải là số hợp lệ.")
    except asyncio.TimeoutError:
        return await ctx.send("Hết thời gian chờ nhập ID tag.")

    # Kiểm tra cookie và lấy fb_dtsg, jazoest
    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    # Đọc nội dung từ nhay.txt
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return await ctx.send("File `nhay.txt` rỗng, vui lòng thêm nội dung.")

    # Tạo task ID duy nhất
    task_id = f"reo_{id_box}_{time.time()}"
    
    async def spam_reo():
        index = 0
        while True:
            # Tạo nội dung tin nhắn với tag người dùng
            content = f"{lines[index]} @[tagged_id:0]"
            success = send_message(id_box, fb_dtsg, jazoest, cookie, content)
            if success:
                print(f"[+] Đã gửi tin nhắn với tag vào box {id_box}: {content}")
            else:
                print(f"[!] Gửi tin nhắn thất bại vào box {id_box}")
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    # Tạo và lưu task
    task = asyncio.create_task(spam_reo())
    running_tasks[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'tagged_id': tagged_id,
        'box_id': id_box
    }
    await ctx.send(f"Đã bắt đầu `reo` vào box `{id_box}` và tag ID `{tagged_id}` với tốc độ `{delay}` giây.")

@bot.command()
async def stopreo(ctx, id_box: str):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")
    
    # Tìm tất cả task liên quan đến id_box
    tasks_to_stop = [task_id for task_id in running_tasks if task_id.startswith(f"reo_{id_box}")]
    
    if not tasks_to_stop:
        return await ctx.send(f"Không có task `reo` nào đang chạy cho box `{id_box}`.")
    
    for task_id in tasks_to_stop:
        if task_info.get(task_id, {}).get('admin_id') == ctx.author.id or ctx.author.id == IDADMIN_GOC:
            running_tasks[task_id].cancel()
            tagged_id = task_info[task_id].get('tagged_id', 'Unknown')
            del running_tasks[task_id]
            del task_info[task_id]
            await ctx.send(f"Đã dừng lệnh `reo` trong box `{id_box}` với tag ID `{tagged_id}`.")
        else:
            await ctx.send(f"Bạn không có quyền dừng task `{task_id}`.")
        
@bot.command()
async def codelag(ctx, id_box: str, cookie: str, speed: float):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    path = "nhay.txt"
    if not os.path.exists(path):
        return await ctx.send("Không tìm thấy file `nhay.txt`.")

    fb_dtsg, jazoest = get_fb_dtsg_jazoest(cookie, id_box)
    if not fb_dtsg:
        return await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")

    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    icon = """"⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰ "⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰ "⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰⃟꙰⃟꙰꙰⃟꙰"""  # Biểu tượng cố định
    task_id = f"codelag_{id_box}_{time.time()}"

    async def loop_codelag():
        index = 0
        while True:
            message = f"{lines[index]} {icon}"
            send_message(id_box, fb_dtsg, jazoest, cookie, message)
            index = (index + 1) % len(lines)
            await asyncio.sleep(speed)

    task = asyncio.create_task(loop_codelag())
    running_tasks[task_id] = task
    task_info[task_id] = {'admin_id': ctx.author.id, 'start_time': time.time()}
    await ctx.send(f"Đã bắt đầu `codelag` vào box `{id_box}` với tốc độ `{speed}` giây.")

# Lệnh stopcodelag
@bot.command()
async def stopcodelag(ctx, id_box: str):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    tasks_to_stop = [task_id for task_id in running_tasks if task_id.startswith(f"codelag_{id_box}")]
    if not tasks_to_stop:
        return await ctx.send(f"Không có task `codelag` nào đang chạy cho box `{id_box}`.")

    for task_id in tasks_to_stop:
        if task_info.get(task_id, {}).get('admin_id') == ctx.author.id:
            running_tasks[task_id].cancel()
            del running_tasks[task_id]
            del task_info[task_id]
            await ctx.send(f"Đã dừng lệnh `codelag` trong box `{id_box}`.")
        else:
            await ctx.send(f"Bạn không có quyền dừng task `{task_id}`.")

@bot.command()
async def tabcodelag(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("codelag_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task codelag nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("codelag_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Box ID: {box_id} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task codelag nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")

# Lệnh tabnhay
@bot.command()
async def tabnhay(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("nhay_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task nhay nào chạy.")

    admin_list = list(admin_task_count.items())

    msg = "**Danh sách admin đang có task:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhay_"):
                box_id = task_id.split("_")[1]
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Box ID: {box_id} | Thời gian chạy: {formatted_time}")

        if not tasks:
            await ctx.send("Admin này không có task nhay nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi.")
def get_guid():
    section_length = int(time.time() * 1000)
    
    def replace_func(c):
        nonlocal section_length
        r = (section_length + random.randint(0, 15)) % 16
        section_length //= 16
        return hex(r if c == "x" else (r & 7) | 8)[2:]

    return "".join(replace_func(c) if c in "xy" else c for c in "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx")

# Hàm chuẩn hóa cookie
def normalize_cookie(cookie, domain='www.facebook.com'):
    headers = {
        'Cookie': cookie,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(f'https://{domain}/', headers=headers, timeout=10)
        if response.status_code == 200:
            set_cookie = response.headers.get('Set-Cookie', '')
            new_tokens = re.findall(r'([a-zA-Z0-9_-]+)=[^;]+', set_cookie)
            cookie_dict = dict(re.findall(r'([a-zA-Z0-9_-]+)=([^;]+)', cookie))
            for token in new_tokens:
                if token not in cookie_dict:
                    cookie_dict[token] = ''
            return ';'.join(f'{k}={v}' for k, v in cookie_dict.items() if v)
    except:
        pass
    return cookie

# Hàm lấy thông tin từ cookie (giữ nguyên theo code bạn gửi)
def get_uid_fbdtsg(ck):
    try:
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Connection': 'keep-alive',
            'Cookie': ck,
            'Host': 'www.facebook.com',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        try:
            response = requests.get('https://www.facebook.com/', headers=headers)
            
            if response.status_code != 200:
                print(f"Status Code >> {response.status_code}")
                return None, None, None, None, None, None
                
            html_content = response.text
            
            user_id = None
            fb_dtsg = None
            jazoest = None
            
            script_tags = re.findall(r'<script id="__eqmc" type="application/json[^>]*>(.*?)</script>', html_content)
            for script in script_tags:
                try:
                    json_data = json.loads(script)
                    if 'u' in json_data:
                        user_param = re.search(r'__user=(\d+)', json_data['u'])
                        if user_param:
                            user_id = user_param.group(1)
                            break
                except:
                    continue
            
            fb_dtsg_match = re.search(r'"f":"([^"]+)"', html_content)
            if fb_dtsg_match:
                fb_dtsg = fb_dtsg_match.group(1)
            
            jazoest_match = re.search(r'jazoest=(\d+)', html_content)
            if jazoest_match:
                jazoest = jazoest_match.group(1)
            
            revision_match = re.search(r'"server_revision":(\d+),"client_revision":(\d+)', html_content)
            rev = revision_match.group(1) if revision_match else ""
            
            a_match = re.search(r'__a=(\d+)', html_content)
            a = a_match.group(1) if a_match else "1"
            
            req = "1b"
                
            return user_id, fb_dtsg, rev, req, a, jazoest
                
        except requests.exceptions.RequestException as e:
            print(f"Lỗi Kết Nối Khi Lấy UID/FB_DTSG: {e}")
            return get_uid_fbdtsg(ck)
            
    except Exception as e:
        print(f"Lỗi: {e}")
        return None, None, None, None, None, None

# Hàm lấy thông tin người dùng (giữ nguyên)
def get_info(uid: str, cookie: str, fb_dtsg: str, a: str, req: str, rev: str) -> Dict[str, Any]:
    try:
        form = {
            "ids[0]": uid,
            "fb_dtsg": fb_dtsg,
            "__a": a,
            "__req": req,
            "__rev": rev
        }
        
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': cookie,
            'Origin': 'https://www.facebook.com',
            'Referer': 'https://www.facebook.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        response = requests.post(
            "https://www.facebook.com/chat/user_info/",
            headers=headers,
            data=form
        )
        
        if response.status_code != 200:
            return {"error": f"Lỗi Kết Nối: {response.status_code}"}
        
        try:
            text_response = response.text
            if text_response.startswith("for (;;);"):
                text_response = text_response[9:]
            
            res_data = json.loads(text_response)
            
            if "error" in res_data:
                return {"error": res_data.get("error")}
            
            if "payload" in res_data and "profiles" in res_data["payload"]:
                return format_data(res_data["payload"]["profiles"])
            else:
                return {"error": f"Không Tìm Thấy Thông Tin Của {uid}"}
                
        except json.JSONDecodeError:
            return {"error": "Lỗi Khi Phân Tích JSON"}
            
    except Exception as e:
        print(f"Lỗi Khi Get Info: {e}")
        return {"error": str(e)}

# Hàm định dạng dữ liệu (giữ nguyên)
def format_data(profiles):
    if not profiles:
        return {"error": "Không Có Data"}
    
    first_profile_id = next(iter(profiles))
    profile = profiles[first_profile_id]
    
    return {
        "id": first_profile_id,
        "name": profile.get("name", ""),
        "url": profile.get("url", ""),
        "thumbSrc": profile.get("thumbSrc", ""),
        "gender": profile.get("gender", "")
    }

# Hàm gửi bình luận (đã sửa lỗi get_guid)
def cmt_gr_pst(cookie, grid, postIDD, ctn, user_id, fb_dtsg, rev, req, a, jazoest, uidtag=None, nametag=None):
    try:
        if not all([user_id, fb_dtsg, jazoest]):
            print("Thiếu user_id, fb_dtsg hoặc jazoest")
            return False
            
        pstid_enc = base64.b64encode(f"feedback:{postIDD}".encode()).decode()
        
        client_mutation_id = str(round(random.random() * 19))
        session_id = get_guid()  # Đã sửa: get_guid() được định nghĩa trước
        crt_time = int(time.time() * 1000)
        
        variables = {
            "feedLocation": "DEDICATED_COMMENTING_SURFACE",
            "feedbackSource": 110,
            "groupID": grid,
            "input": {
                "client_mutation_id": client_mutation_id,
                "actor_id": user_id,
                "attachments": None,
                "feedback_id": pstid_enc,
                "formatting_style": None,
                "message": {
                    "ranges": [],
                    "text": ctn
                },
                "attribution_id_v2": f"SearchCometGlobalSearchDefaultTabRoot.react,comet.search_results.default_tab,tap_search_bar,{crt_time},775647,391724414624676,,",
                "vod_video_timestamp": None,
                "is_tracking_encrypted": True,
                "tracking": [],
                "feedback_source": "DEDICATED_COMMENTING_SURFACE",
                "session_id": session_id
            },
            "inviteShortLinkKey": None,
            "renderLocation": None,
            "scale": 3,
            "useDefaultActor": False,
            "focusCommentID": None,
            "__relay_internal__pv__IsWorkUserrelayprovider": False
        }
        
        if uidtag and nametag:
            name_position = ctn.find(nametag)
            if name_position != -1:
                variables["input"]["message"]["ranges"] = [
                    {
                        "entity": {
                            "id": uidtag
                        },
                        "length": len(nametag),
                        "offset": name_position
                    }
                ]
            
        payload = {
            'av': user_id,
            '__crn': 'comet.fbweb.CometGroupDiscussionRoute',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest,
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'useCometUFICreateCommentMutation',
            'variables': json.dumps(variables),
            'server_timestamps': 'true',
            'doc_id': '24323081780615819'
        }
        
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': cookie,
            'Origin': 'https://www.facebook.com',
            'Referer': f'https://www.facebook.com/groups/{grid}',
            'User-Agent': 'python-http/0.27.0'
        }
        
        response = requests.post('https://www.facebook.com/api/graphql', data=payload, headers=headers)
        print(f"Mã trạng thái cho bài {postIDD}: {response.status_code}")
        print(f"Phản hồi: {response.text[:500]}...")  # In 500 ký tự đầu
        
        if response.status_code == 200:
            try:
                json_response = response.json()
                if 'errors' in json_response:
                    print(f"Lỗi GraphQL: {json_response['errors']}")
                    return False
                if 'data' in json_response and 'comment_create' in json_response['data']:
                    print("Bình luận đã được đăng")
                    return True
                print("Không tìm thấy comment_create trong phản hồi")
                return False
            except ValueError:
                print("Phản hồi JSON không hợp lệ")
                return False
        else:
            return False
    except Exception as e:
        print(f"Lỗi khi gửi bình luận: {e}")
        return False

# Hàm lấy ID bài viết và nhóm
def extract_post_group_id(post_link):
    post_match = re.search(r'facebook\.com/.+/permalink/(\d+)', post_link)
    group_match = re.search(r'facebook\.com/groups/(\d+)', post_link)
    if not post_match or not group_match:
        return None, None
    return post_match.group(1), group_match.group(1)

# Lệnh nhaytop
@bot.command()
async def nhaytop(ctx, cookie: str, delay: float):
    if ctx.author.id not in admins:
        await ctx.send("Bạn không có quyền sử dụng lệnh này.")
        return

    # Kiểm tra file nhay.txt
    path = "nhay.txt"
    if not os.path.exists(path):
        await ctx.send("Không tìm thấy file `nhay.txt`.")
        return

    # Yêu cầu link bài viết
    await ctx.send("Vui lòng nhập link bài viết (ví dụ: https://facebook.com/groups/123/permalink/456):")
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    try:
        msg = await bot.wait_for('message', timeout=30.0, check=check)
        post_link = msg.content.strip()
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ nhập link bài viết.")
        return

    # Lấy post_id và group_id
    post_id, group_id = extract_post_group_id(post_link)
    if not post_id or not group_id:
        await ctx.send("Link bài viết không hợp lệ hoặc không tìm được group_id.")
        return

    # Chuẩn hóa cookie
    cookie = normalize_cookie(cookie)
    
    # Kiểm tra cookie
    user_id, fb_dtsg, rev, req, a, jazoest = get_uid_fbdtsg(cookie)
    if not user_id or not fb_dtsg or not jazoest:
        await ctx.send("Cookie không hợp lệ hoặc không lấy được thông tin.")
        return

    # Đọc nội dung từ nhay.txt
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        await ctx.send("File `nhay.txt` rỗng.")
        return

    task_id = f"nhaytop_{post_id}_{time.time()}"
    
    async def loop_nhaytop():
        index = 0
        while True:
            message = lines[index]
            success = cmt_gr_pst(cookie, group_id, post_id, message, user_id, fb_dtsg, rev, req, a, jazoest)
            if success:
                print(f"[+] Đã gửi bình luận vào bài {post_id}: {message}")  # Thông báo trên Termux
            else:
                print(f"[!] Gửi bình luận thất bại vào bài {post_id}")  # Thông báo trên Termux
            index = (index + 1) % len(lines)
            await asyncio.sleep(delay)

    task = asyncio.create_task(loop_nhaytop())
    running_tasks[task_id] = task
    task_info[task_id] = {
        'admin_id': ctx.author.id,
        'start_time': time.time(),
        'post_id': post_id,
        'group_id': group_id
    }
    await ctx.send(f"Đã bắt đầu `nhaytop` vào bài viết `{post_id}` với tốc độ `{delay}` giây.")
@bot.command()
async def stopnhaytop(ctx):
    if ctx.author.id not in admins:
        return await ctx.send("Bạn không có quyền sử dụng lệnh này.")

    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("nhaytop_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task nhaytop nào chạy.")

    admin_list = list(admin_task_count.items())
    msg = "**Danh sách admin đang có task nhaytop:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        if selected_admin_id != ctx.author.id:
            return await ctx.send("Bạn chỉ có thể dừng task do chính mình tạo.")

        tasks = []
        task_mapping = {}
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhaytop_"):
                post_id = info['post_id']
                group_id = info['group_id']
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                task_index = len(tasks) + 1
                tasks.append(f"{task_index}. Group ID: {group_id}, Post ID: {post_id} (chạy được {formatted_time})")
                task_mapping[task_index] = task_id

        if not tasks:
            return await ctx.send("Admin này không có task nhaytop nào.")

        await ctx.send("**Danh sách task của admin đã chọn:**\n" + "\n".join(tasks) + "\n\nNhập số task để dừng (ví dụ: 1, 2) hoặc 'all' để dừng tất cả.")

        reply = await bot.wait_for('message', timeout=30.0, check=check)
        user_input = reply.content.strip().lower()

        if user_input == "all":
            stopped_tasks = []
            for task_index, task_id in task_mapping.items():
                running_tasks[task_id].cancel()
                start_time = task_info[task_id]['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                group_id = task_info[task_id]['group_id']
                post_id = task_info[task_id]['post_id']
                stopped_tasks.append(f"Task Group ID: {group_id}, Post ID: {post_id} (chạy được {formatted_time})")
                del running_tasks[task_id]
                del task_info[task_id]
            await ctx.send(f"Đã dừng tất cả task:\n" + "\n".join(stopped_tasks))
        else:
            task_index = int(user_input)
            if task_index not in task_mapping:
                return await ctx.send("Số task không hợp lệ.")
            
            task_id = task_mapping[task_index]
            running_tasks[task_id].cancel()
            start_time = task_info[task_id]['start_time']
            delta = datetime.now() - datetime.fromtimestamp(start_time)
            formatted_time = str(delta).split('.')[0]
            group_id = task_info[task_id]['group_id']
            post_id = task_info[task_id]['post_id']
            del running_tasks[task_id]
            del task_info[task_id]
            await ctx.send(f"Đã dừng task Group ID: `{group_id}`, Post ID: `{post_id}` (chạy được {formatted_time}).")

    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except ValueError:
        await ctx.send("Vui lòng nhập số hợp lệ hoặc 'all'.")
    except Exception as e:
        await ctx.send(f"Đã xảy ra lỗi: {str(e)}")

@bot.command()
async def tabnhaytop(ctx):
    admin_task_count = {}
    for task_id, info in task_info.items():
        if task_id.startswith("nhaytop_"):
            admin_id = info['admin_id']
            admin_task_count[admin_id] = admin_task_count.get(admin_id, 0) + 1

    if not admin_task_count:
        return await ctx.send("Hiện không có task nhaytop nào chạy.")

    admin_list = list(admin_task_count.items())
    msg = "**Danh sách admin đang có task nhaytop:**\n"
    for i, (admin_id, count) in enumerate(admin_list, start=1):
        try:
            user = await bot.fetch_user(admin_id)
            msg += f"{i}. Admin {user.mention} đã tạo {count} task.\n"
        except:
            msg += f"{i}. Admin ID {admin_id} đã tạo {count} task.\n"

    msg += "\nNhập số (ví dụ: 1, 2) để xem task của admin tương ứng."
    await ctx.send(msg)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for('message', timeout=30.0, check=check)
        index = int(reply.content.strip()) - 1
        if index < 0 or index >= len(admin_list):
            return await ctx.send("Số không hợp lệ.")

        selected_admin_id = admin_list[index][0]
        tasks = []
        for task_id, info in task_info.items():
            if info['admin_id'] == selected_admin_id and task_id.startswith("nhaytop_"):
                post_id = info['post_id']
                group_id = info['group_id']
                start_time = info['start_time']
                delta = datetime.now() - datetime.fromtimestamp(start_time)
                formatted_time = str(delta).split('.')[0]
                tasks.append(f"Group ID: {group_id}, Post ID: {post_id}\nThời gian chạy: {formatted_time}\n\n")

        if not tasks:
            await ctx.send("Admin này không có task nhaytop nào.")
        else:
            await ctx.send("**Các task của admin đã chọn:**\n" + "\n".join(tasks))
    except asyncio.TimeoutError:
        await ctx.send("Hết thời gian chờ, vui lòng thử lại sau.")
    except ValueError:
        await ctx.send("Vui lòng nhập số hợp lệ.")
    except Exception as e:
        await ctx.send(f"Đã xảy ra lỗi: {str(e)}")

# Menu bình thường

@bot.command()
async def menu(ctx):
    # Tạo embed
    embed = discord.Embed(
        title="『 **Menu Bot By La Minh Lợi 💬 Sever Anh Em Sát Thần**』",
        description=f"""
Admin: La Minh Lợi 
Bot By: La Minh Lợi 
Zalo: **
Facebook: [Click vào đây](https://www.facebook.com/profile.php?id=100087637635614)
Prefix: `{PREFIX}`

**Admin & Quản lý**
🔷 `{PREFIX}addadmin @tag` – Thêm admin
🔷 `{PREFIX}deladmin @tag` – Xoá admin
🔷 `{PREFIX}listadmin` – xem danh sách admin
**Treo Messenger**
🔷 `{PREFIX}setngonmess [file]`
🔷 `{PREFIX}ngonmess <id> <cookie> <file> <delay>`
🔷 `{PREFIX}stopngonmess <id>`
🔷 `{PREFIX}xemngonmes`
🔷 `{PREFIX}tabngonmess`
**Réo Messenger**
🔷 `{PREFIX}reo <idbox> <cookie> <delay>`
🔷 `{PREFIX}stopreo`
**Nhây Messenger**
🔷 `{PREFIX}nhay <id> <cookie> <deylay>`
🔷 `{PREFIX}stopnhay <id>`
🔷 `{PREFIX}tabnhay`
**Codelag Messenger**
🔷 `{PREFIX}codelag <id> <cookie> <deylay>`
🔷 `{PREFIX}stopcodekag <id>`
🔷 `{PREFIX}tabcodelag`
**Nhây Top Facebook**
🔷`{PREFIX}nhaytop <cookie> <deylay>`
🔷`{PREFIX}stopnhaytop`
🔷`{PREFIX}tabnhaytop`
 **Thông tin**
 🔷 Admin Điều Hành: <@{IDADMIN_GOC}>
""",
        color=discord.Color.blue()
    )

    embed.set_footer(text=f"Bot By Minh Lợi 💬 | Admin ID: {IDADMIN_GOC}")
    embed.set_image(url="https://i.imgur.com/ZooGZrk.jpeg")  # Gắn ảnh vào embed

    # Mở file ảnh, gửi kèm ảnh + embed cùng lúc
    with open('menu.jpg', 'rb') as f:
        file = discord.File(f, filename='menu.jpg')
        await ctx.send(embed=embed, file=file)
        
bot.run(TOKEN)
