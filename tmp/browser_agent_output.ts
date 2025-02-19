import express from 'express';
import puppeteer from 'puppeteer';

const app = express();
const PORT = 3000;

// 启动Puppeteer浏览器实例
let browser: puppeteer.Browser;

async function startBrowser() {
    browser = await puppeteer.launch({ headless: true });
}

startBrowser().catch(console.error);

// 定义一个API端点来触发浏览器自动化操作
app.get('/automate', async (req, res) => {
    try {
        if (!browser) {
            throw new Error('Browser not initialized');
        }

        const page = await browser.newPage();
        await page.goto('https://www.baidu.com'); // 替换为你想要访问的URL
        await page.screenshot({ path: 'example.png' }); // 截图保存到example.png

        await page.close();
        res.send('Automation completed successfully');
    } catch (error) {
        console.error(error);
        res.status(500).send('Automation failed');
    }
});

// 添加处理根路径的路由
app.get('/', (req, res) => {
    res.send('Welcome to the MCP Server');
});

// 启动Express服务器
app.listen(PORT, () => {
    console.log(`MCP server is running on http://localhost:${PORT}`);
});