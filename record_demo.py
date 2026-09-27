import asyncio
import os
from playwright.async_api import async_playwright

APP_URL = "https://wayfarer-frontend-377275652286.us-east1.run.app"
ARTIFACTS_DIR = "/config/.gemini/antigravity/brain/3a13a67b-13f8-45e1-b4a2-db8cdde61d27"

async def smooth_scroll_down(page):
    """Smoothly scroll the #log chat container to the bottom."""
    await page.evaluate("""
        const log = document.getElementById("log");
        if (log) log.scrollTo({ top: log.scrollHeight, behavior: 'smooth' });
    """)
    await page.wait_for_timeout(1500)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            record_video_dir=ARTIFACTS_DIR,
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        print(f"Navigating to {APP_URL}...")
        await page.goto(APP_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # 1. First prompt: Click example chip 1 (Tokyo)
        print("Clicking first prompt chip (Tokyo itinerary)...")
        chips = await page.query_selector_all(".prompt-chip")
        if chips and len(chips) >= 1:
            await chips[0].click()
        else:
            await page.fill("#input", "🌍 Plan a 3-day trip to Tokyo with budget")
            await page.click("button")
            
        print("Waiting for first response...")
        await page.wait_for_selector(".msg.agent .bubble", timeout=60000)
        for _ in range(60):
            content = await page.inner_text(".msg.agent .bubble")
            if content and content.strip() != "…":
                break
            await asyncio.sleep(1)
            
        await page.wait_for_timeout(3000)
        await smooth_scroll_down(page)
        
        # 2. Second prompt: Paris food spots & postcard preview
        print("Sending second prompt (Paris dining spots & postcard preview)...")
        await page.fill("#input", "🥐 Find top food & dining spots in Paris and generate a postcard preview")
        await page.click("button")
        
        print("Waiting for second response...")
        await page.wait_for_selector(".msg.agent:nth-of-type(2) .bubble", timeout=60000)
        for _ in range(60):
            agent_bubbles = await page.query_selector_all(".msg.agent .bubble")
            if len(agent_bubbles) >= 2:
                last_text = await agent_bubbles[-1].inner_text()
                if last_text and last_text.strip() != "…":
                    break
            await asyncio.sleep(1)
            
        await page.wait_for_timeout(4000)
        await smooth_scroll_down(page)

        # 3. Third prompt: Postcard preview for Bali
        print("Sending third prompt (Postcard preview for Bali)...")
        chips = await page.query_selector_all(".prompt-chip")
        if chips and len(chips) >= 3:
            await chips[2].click()
        else:
            await page.fill("#input", "📸 Generate a postcard preview for Bali")
            await page.click("button")

        print("Waiting for third response...")
        for _ in range(90):
            agent_bubbles = await page.query_selector_all(".msg.agent .bubble")
            if len(agent_bubbles) >= 3:
                last_bubble = agent_bubbles[-1]
                img = await last_bubble.query_selector("img")
                txt = await last_bubble.inner_text()
                if img or (txt and txt.strip() != "…"):
                    break
            await asyncio.sleep(1)

        await page.wait_for_timeout(8000)
        await smooth_scroll_down(page)
        await page.wait_for_timeout(4000)
        
        video_obj = page.video
        await context.close()
        await browser.close()
        
        if video_obj:
            video_path = await video_obj.path()
            target_file = os.path.join(ARTIFACTS_DIR, "demo_recording.webm")
            if os.path.exists(video_path):
                os.rename(video_path, target_file)
                print(f"SUCCESS: Video saved to {target_file}")

if __name__ == "__main__":
    asyncio.run(main())
