import sys

with open('telegram_sniper.py', encoding='utf-8') as f:
    content = f.read()

# Add aiohttp import at the top
if 'from aiohttp import web' not in content:
    content = content.replace('import asyncio', 'import asyncio\nfrom aiohttp import web\nimport os')

# Add the dummy web server setup right before `async def main():`
web_server_code = '''
# ============================================================
# Dummy Web Server (For Render Deployment)
# ============================================================
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"[+] Dummy Web Server is listening on port {port} 🌐")

'''

if '# Dummy Web Server' not in content:
    content = content.replace('async def main():', web_server_code + 'async def main():')

# Add `await start_web_server()` inside `main()`
if 'await start_web_server()' not in content:
    content = content.replace('await client.start()', 'await start_web_server()\n    await client.start()')

with open('telegram_sniper.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Added dummy web server for Render.")
