import asyncio
import os
import shutil
import time
from playwright.async_api import async_playwright

FRONTEND_URL = "https://sprout-advisor-frontend-273799513932.us-east1.run.app"
ARTIFACTS_DIR = "/config/.gemini/antigravity/brain/51d94ad1-1a20-4599-9670-cf1515f96f89"
SCRATCH_DIR = "/tmp/demo_videos"

async def record_demo():
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    async with async_playwright() as p:
        print("Launching Chromium with video recording...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=SCRATCH_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print(f"Navigating to {FRONTEND_URL}...")
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # 1. First prompt: Click 1st prompt chip (Zone 6a frontyard flowers - core app capability)
        print("Clicking 1st prompt chip (🌸 Flowers for sunny frontyard)...")
        chip1 = page.locator(".chip").first
        await chip1.click()
        await asyncio.sleep(12) # Allow agent response to render dialogue bubble

        # 2. Second, richer prompt: Tool calls (Soil calculation & live weather)
        second_prompt = "Calculate how much soil I need for a 4x8 raised bed that is 1 foot deep, and check current local weather for my Zone 6a garden."
        print(f"Submitting 2nd prompt: {second_prompt}")
        
        input_box = page.locator("#input")
        await input_box.fill("")
        for char in second_prompt:
            await input_box.type(char, delay=25)
            
        send_btn = page.locator("button:has-text('Send')")
        await send_btn.click()
        await asyncio.sleep(14) # Allow agent tool calls & response rendering

        # Final smooth scroll down to showcase full conversation dialogue
        await page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        await asyncio.sleep(3)

        video_path = await page.video.path()
        await context.close()
        await browser.close()
        
        target_path = os.path.join(ARTIFACTS_DIR, "sprout_advisor_demo.webm")
        shutil.copy(video_path, target_path)
        print(f"Demo video saved successfully to {target_path}")

if __name__ == "__main__":
    asyncio.run(record_demo())
