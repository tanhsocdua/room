# -*- coding: utf-8 -*-
"""
Discord Voice Player - Treo room phát MP3 (Bot Token)
Đã sửa lỗi voice_clients
"""

import discord
from discord.ext import commands
import asyncio
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional
import glob
import random

# ==================== CẤU HÌNH ====================
BOT_TOKEN = input("🔑 Nhập Bot Token: ").strip()
VOICE_CHANNEL_ID = int(input("🎤 Nhập ID phòng voice: ").strip())

# Lấy thư mục chứa script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_FOLDER = os.path.join(SCRIPT_DIR, "music")

# Tạo thư mục music nếu chưa có
os.makedirs(MUSIC_FOLDER, exist_ok=True)

# Tìm file MP3
def find_mp3_files():
    mp3_files = []
    mp3_files.extend(glob.glob(os.path.join(MUSIC_FOLDER, "*.mp3")))
    mp3_files.extend(glob.glob(os.path.join(SCRIPT_DIR, "*.mp3")))
    return mp3_files

mp3_files = find_mp3_files()
if not mp3_files:
    print("❌ Không tìm thấy file MP3 nào!")
    print(f"📁 Hãy đặt file MP3 vào thư mục: {MUSIC_FOLDER} hoặc thư mục chính")
    sys.exit()

DEFAULT_MP3 = mp3_files[0]
print(f"✅ Sử dụng file mặc định: {os.path.basename(DEFAULT_MP3)}")
print(f"📁 Tổng số file MP3 tìm thấy: {len(mp3_files)}")

# ==================== BOT ====================
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=["!", "/"], intents=intents)

# Xóa lệnh help mặc định
bot.remove_command('help')

vc: Optional[discord.VoiceClient] = None
is_playing = False
current_mp3 = DEFAULT_MP3
playlist = mp3_files.copy()
current_index = 0
reconnect_count = 0
volume_level = 0.5
loop_mode = "loop_one"
auto_play = True

@bot.event
async def on_ready():
    print(f"\n✅ Bot đã đăng nhập: {bot.user}")
    print(f"📊 Số server: {len(bot.guilds)}")
    print(f"🎵 Số bài hát trong playlist: {len(playlist)}")
    print("=" * 50)
    await connect_to_voice()

async def connect_to_voice():
    """Kết nối vào phòng voice với cơ chế retry"""
    global vc, reconnect_count
    try:
        channel = bot.get_channel(VOICE_CHANNEL_ID)
        if not channel:
            print(f"❌ Không tìm thấy phòng voice ID: {VOICE_CHANNEL_ID}")
            return

        # Kiểm tra bot đã kết nối chưa (CÁCH SỬA MỚI)
        if vc and vc.is_connected():
            return

        # Kiểm tra xem bot đã ở trong phòng voice nào chưa (CÁCH SỬA MỚI)
        for guild in bot.guilds:
            # Lấy voice client của guild hiện tại
            voice_client = guild.voice_client
            if voice_client and voice_client.channel.id == VOICE_CHANNEL_ID:
                vc = voice_client
                print(f"✅ Đã kết nối vào phòng: {channel.name}")
                if auto_play and not is_playing:
                    await play_loop()
                return

        # Nếu chưa kết nối, tạo kết nối mới
        vc = await channel.connect()
        reconnect_count = 0
        print(f"✅ Đã kết nối vào phòng: {channel.name}")
        print(f"📊 Số người trong phòng: {len(channel.members)}")
        
        if auto_play and len(channel.members) > 1 and not is_playing:
            await play_loop()
            
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        reconnect_count += 1
        if reconnect_count < 10:
            wait = min(5 * reconnect_count, 60)
            print(f"🔄 Thử lại sau {wait}s...")
            await asyncio.sleep(wait)
            await connect_to_voice()

def after_playing(error):
    """Callback sau khi phát xong"""
    global is_playing
    is_playing = False
    if error:
        print(f"❌ Lỗi phát nhạc: {error}")
    else:
        asyncio.run_coroutine_threadsafe(handle_next_song(), bot.loop)

async def handle_next_song():
    """Xử lý bài hát tiếp theo theo chế độ loop"""
    global current_index, playlist, loop_mode, current_mp3
    
    if not playlist:
        return
    
    if loop_mode == "loop_one":
        pass
    elif loop_mode == "loop_all":
        current_index = (current_index + 1) % len(playlist)
        current_mp3 = playlist[current_index]
    elif loop_mode == "shuffle":
        current_mp3 = random.choice(playlist)
    elif loop_mode == "none":
        return
    
    await play_loop()

async def play_loop():
    """Vòng lặp phát nhạc"""
    global vc, is_playing, current_mp3, volume_level
    
    if not vc or not vc.is_connected():
        return
    
    if is_playing:
        return
    
    if not os.path.exists(current_mp3):
        print(f"❌ Không tìm thấy file: {current_mp3}")
        mp3_files = find_mp3_files()
        if mp3_files:
            current_mp3 = mp3_files[0]
            print(f"🔄 Chuyển sang file: {os.path.basename(current_mp3)}")
        else:
            return
    
    try:
        ffmpeg_options = {}
        if volume_level != 1.0:
            ffmpeg_options['before_options'] = f'-filter:a "volume={volume_level}"'
        
        source = discord.FFmpegPCMAudio(current_mp3, **ffmpeg_options)
        
        vc.play(source, after=after_playing)
        is_playing = True
        print(f"🎵 Đang phát: {os.path.basename(current_mp3)}")
        print(f"🔊 Âm lượng: {int(volume_level * 100)}%")
        print(f"🔄 Chế độ loop: {loop_mode}")
        
    except Exception as e:
        print(f"❌ Lỗi phát nhạc: {e}")
        is_playing = False
        await asyncio.sleep(2)

@bot.event
async def on_voice_state_update(member, before, after):
    """Xử lý khi có người vào/ra phòng voice"""
    if member == bot.user:
        return
    
    if after.channel and after.channel.id == VOICE_CHANNEL_ID:
        if vc and vc.is_connected() and auto_play:
            if not is_playing:
                print(f"👤 {member.display_name} vào phòng - Phát nhạc!")
                await play_loop()
    
    if before.channel and before.channel.id == VOICE_CHANNEL_ID:
        channel = bot.get_channel(VOICE_CHANNEL_ID)
        if channel and len(channel.members) <= 1:
            if auto_play and is_playing:
                print("🔇 Phòng trống - Tạm dừng phát nhạc")
                if vc and vc.is_playing():
                    vc.pause()

@bot.event
async def on_command_error(ctx, error):
    """Xử lý lỗi lệnh"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Lệnh không tồn tại! Gõ `!help` để xem danh sách lệnh.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Thiếu tham số! Ví dụ: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Tham số không hợp lệ! {error}")
        return
    await ctx.send(f"❌ Lỗi: {error}")

# ==================== LỆNH ĐIỀU KHIỂN ====================

@bot.command(name='play', aliases=['p', 'phat'])
async def play_cmd(ctx, *, filename: str = None):
    """Phát nhạc - !play [tên file]"""
    global vc, is_playing, current_mp3
    
    if not vc or not vc.is_connected():
        await ctx.send("❌ Chưa kết nối voice! Dùng `!join`")
        return
    
    if filename:
        mp3_files = find_mp3_files()
        found = None
        for f in mp3_files:
            if filename.lower() in os.path.basename(f).lower():
                found = f
                break
        
        if found:
            current_mp3 = found
            if vc.is_playing():
                vc.stop()
            await ctx.send(f"🎵 Chuyển sang bài: {os.path.basename(current_mp3)}")
            await play_loop()
        else:
            await ctx.send(f"❌ Không tìm thấy file MP3 có tên: {filename}")
    else:
        if is_playing:
            await ctx.send("⏭️ Đang phát rồi!")
            return
        await play_loop()
        await ctx.send(f"🎵 Đang phát: {os.path.basename(current_mp3)}")

@bot.command(name='stop', aliases=['s', 'dung'])
async def stop_cmd(ctx):
    """Dừng phát nhạc"""
    global vc, is_playing
    if vc and vc.is_playing():
        vc.stop()
        is_playing = False
        await ctx.send("⏹️ Đã dừng phát nhạc!")

@bot.command(name='pause', aliases=['tamdung'])
async def pause_cmd(ctx):
    """Tạm dừng phát nhạc"""
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸️ Đã tạm dừng!")
    else:
        await ctx.send("❌ Không có nhạc đang phát!")

@bot.command(name='resume', aliases=['tieptuc'])
async def resume_cmd(ctx):
    """Tiếp tục phát nhạc"""
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶️ Tiếp tục phát!")
    else:
        await ctx.send("❌ Không có nhạc đang tạm dừng!")

@bot.command(name='skip', aliases=['next', 'boqua'])
async def skip_cmd(ctx):
    """Bỏ qua bài hiện tại"""
    global vc, is_playing
    if vc and vc.is_playing():
        vc.stop()
        is_playing = False
        await ctx.send("⏭️ Đã bỏ qua bài hiện tại!")
        await play_loop()
    else:
        await ctx.send("❌ Không có nhạc đang phát!")

@bot.command(name='volume', aliases=['vol', 'amluong'])
async def volume_cmd(ctx, vol: int):
    """Chỉnh âm lượng - !volume 50"""
    global volume_level
    if not (0 <= vol <= 100):
        await ctx.send("❌ Âm lượng phải từ 0-100")
        return
    
    volume_level = vol / 100
    if vc and vc.is_playing():
        vc.stop()
        await play_loop()
    
    await ctx.send(f"🔊 Đã chỉnh âm lượng: {vol}%")

@bot.command(name='loop', aliases=['lap'])
async def loop_cmd(ctx, mode: str = None):
    """Chế độ lặp - !loop [one/all/shuffle/none]"""
    global loop_mode
    modes = {
        'one': 'loop_one',
        'all': 'loop_all', 
        'shuffle': 'shuffle',
        'none': 'none'
    }
    
    if mode and mode.lower() in modes:
        loop_mode = modes[mode.lower()]
        await ctx.send(f"🔄 Đã chuyển sang chế độ: **{mode.upper()}**")
    else:
        mode_names = {
            'loop_one': '🔁 Phát lại bài hiện tại',
            'loop_all': '🔁 Phát toàn bộ playlist',
            'shuffle': '🎲 Phát ngẫu nhiên',
            'none': '⏹️ Không lặp'
        }
        await ctx.send(f"📌 Chế độ lặp hiện tại: {mode_names.get(loop_mode, loop_mode)}")
        await ctx.send("💡 Cách dùng: `!loop one/all/shuffle/none`")

@bot.command(name='playlist', aliases=['pl', 'danhsach'])
async def playlist_cmd(ctx):
    """Hiển thị danh sách nhạc"""
    mp3_files = find_mp3_files()
    if not mp3_files:
        await ctx.send("📁 Không có file MP3 nào!")
        return
    
    display = []
    for i, f in enumerate(mp3_files[:20], 1):
        name = os.path.basename(f)
        if f == current_mp3:
            name = f"▶️ {name}"
        display.append(f"{i}. {name}")
    
    if len(mp3_files) > 20:
        display.append(f"... và {len(mp3_files) - 20} bài khác")
    
    await ctx.send(f"📋 **Danh sách nhạc ({len(mp3_files)} bài):**\n" + "\n".join(display))

@bot.command(name='join', aliases=['j', 'vao'])
async def join_cmd(ctx):
    """Bot vào phòng voice"""
    await connect_to_voice()
    await ctx.send("✅ Đã kết nối voice!")

@bot.command(name='leave', aliases=['disconnect', 'dc', 'ra'])
async def leave_cmd(ctx):
    """Bot rời phòng voice"""
    global vc, is_playing
    if vc and vc.is_connected():
        if vc.is_playing():
            vc.stop()
        await vc.disconnect()
        vc = None
        is_playing = False
        await ctx.send("🔌 Đã ngắt kết nối voice!")

@bot.command(name='autoplay', aliases=['auto'])
async def autoplay_cmd(ctx, mode: str = None):
    """Bật/tắt auto play - !autoplay on/off"""
    global auto_play
    if mode and mode.lower() in ['on', 'off']:
        auto_play = mode.lower() == 'on'
        await ctx.send(f"✅ Auto play: {'BẬT' if auto_play else 'TẮT'}")
    else:
        await ctx.send(f"📌 Auto play hiện tại: {'BẬT' if auto_play else 'TẮT'}")

@bot.command(name='status', aliases=['st', 'tt'])
async def status_cmd(ctx):
    """Xem trạng thái bot"""
    channel = bot.get_channel(VOICE_CHANNEL_ID)
    status = f"""
📊 **TRẠNG THÁI BOT**

🔌 Kết nối: {'✅' if vc and vc.is_connected() else '❌'}
🎵 Đang phát: {'✅' if is_playing else '❌'}
🎚️ Âm lượng: {int(volume_level * 100)}%
🔄 Chế độ lặp: {loop_mode}
🎤 Số người trong phòng: {len(channel.members) if channel else 0}
📁 Số file MP3: {len(find_mp3_files())}
🎵 File hiện tại: {os.path.basename(current_mp3)}
🔄 Số lần reconnect: {reconnect_count}
🤖 Auto play: {'✅' if auto_play else '❌'}
"""
    await ctx.send(status)

@bot.command(name='help', aliases=['h', 'trogiup'])
async def help_cmd(ctx):
    """Hiển thị danh sách lệnh"""
    embed = discord.Embed(
        title="🎵 DISCORD MUSIC BOT - HƯỚNG DẪN",
        description="Tất cả lệnh có thể dùng với prefix `!` hoặc `/`",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎵 Lệnh phát nhạc",
        value=(
            "`!play [tên]` - Phát nhạc / Tìm bài\n"
            "`!stop` - Dừng phát\n"
            "`!pause` - Tạm dừng\n"
            "`!resume` - Tiếp tục\n"
            "`!skip` - Bỏ qua bài\n"
            "`!volume <0-100>` - Chỉnh âm lượng"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📋 Quản lý playlist",
        value=(
            "`!playlist` - Xem danh sách nhạc\n"
            "`!loop [one/all/shuffle/none]` - Chế độ lặp\n"
            "`!autoplay on/off` - Tự động phát khi có người"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔌 Lệnh voice",
        value=(
            "`!join` - Vào phòng voice\n"
            "`!leave` - Rời phòng\n"
            "`!status` - Xem trạng thái"
        ),
        inline=False
    )
    
    embed.set_footer(text="💡 Gợi ý: Thêm file MP3 vào thư mục 'music' để tự động load")
    await ctx.send(embed=embed)

@bot.command(name='reload', aliases=['load', 'tailai'])
async def reload_cmd(ctx):
    """Tải lại danh sách nhạc"""
    global playlist, mp3_files
    mp3_files = find_mp3_files()
    playlist = mp3_files.copy()
    await ctx.send(f"✅ Đã tải lại danh sách nhạc! Tìm thấy {len(playlist)} bài.")

@bot.command(name='now', aliases=['current', 'dangphat'])
async def now_cmd(ctx):
    """Hiển thị bài đang phát"""
    if is_playing:
        await ctx.send(f"🎵 **Đang phát:** {os.path.basename(current_mp3)}")
    else:
        await ctx.send("❌ Không có nhạc đang phát!")

# ==================== CHẠY ====================
if __name__ == "__main__":
    print("""
    ═══════════════════════════════════════
       🎵 DISCORD VOICE PLAYER
       Phát MP3 vô tận với nhiều tính năng
    ═══════════════════════════════════════
    """)
    
    # Kiểm tra FFmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ FFmpeg đã được tìm thấy")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Không tìm thấy FFmpeg!")
        print("📥 Tải tại: https://www.gyan.dev/ffmpeg/builds/")
        print("📂 Giải nén vào C:\\ffmpeg và thêm vào PATH")
        sys.exit()
    
    print(f"🎤 Phòng voice ID: {VOICE_CHANNEL_ID}")
    print(f"🎵 File mặc định: {os.path.basename(current_mp3)}")
    print(f"📁 Số file MP3: {len(find_mp3_files())}")
    print("=" * 50)
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        print("❌ Token bot không hợp lệ!")
    except KeyboardInterrupt:
        print("\n🛑 Đã dừng chương trình.")
        asyncio.run(bot.close())
