const express = require('express');
const cors = require('cors');
const { Agent } = require('@cursor/sdk');

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

app.post('/v1/chat/completions', async (req, res) => {
    try {
        const { messages, model, stream } = req.body;
        const apiKey = process.env.CURSOR_API_KEY;

        if (!apiKey) {
            return res.status(401).json({ error: 'CURSOR_API_KEY is not set' });
        }

        // Convert messages to a single prompt string since Cursor SDK typically uses agent.send(prompt)
        const prompt = messages.map(m => {
            let text = m.content;
            if (Array.isArray(m.content)) {
                text = m.content.map(c => c.text || JSON.stringify(c)).join('\n');
            } else if (typeof m.content === 'object') {
                text = JSON.stringify(m.content);
            }
            return `${m.role.toUpperCase()}:\n${text}`;
        }).join('\n\n');

        const agent = await Agent.create({
            apiKey: apiKey,
            model: { id: model || 'composer-2.5' },
        });

        const run = await agent.send(prompt);

        if (stream) {
            res.setHeader('Content-Type', 'text/event-stream');
            res.setHeader('Cache-Control', 'no-cache');
            res.setHeader('Connection', 'keep-alive');

            // We stream the chunks back to the client in OpenAI format
            for await (const event of run.stream()) {
                if (event.type === 'assistant' && event.message && event.message.content) {
                    const textBlocks = event.message.content.filter(c => c.type === 'text');
                    if (textBlocks.length > 0) {
                        const textDelta = textBlocks.map(c => c.text).join('');
                        const chunk = {
                            id: 'chatcmpl-cursor',
                            object: 'chat.completion.chunk',
                            created: Date.now(),
                            model: model || 'composer-2.5',
                            choices: [{
                                delta: { content: textDelta },
                                index: 0,
                                finish_reason: null
                            }]
                        };
                        res.write(`data: ${JSON.stringify(chunk)}\n\n`);
                    }
                }
                // If it's a tool call (Cursor SDK might run it automatically, we just inform the user)
                if (event.type === 'ShellOutputSchema') {
                     const chunk = {
                        id: 'chatcmpl-cursor',
                        object: 'chat.completion.chunk',
                        created: Date.now(),
                        model: model || 'composer-2.5',
                        choices: [{
                            delta: { content: `\n[Cursor Executed Command: ${event.command}]\n${event.output}\n` },
                            index: 0,
                            finish_reason: null
                        }]
                    };
                    res.write(`data: ${JSON.stringify(chunk)}\n\n`);
                }
            }

            const finalChunk = {
                id: 'chatcmpl-cursor',
                object: 'chat.completion.chunk',
                created: Date.now(),
                model: model || 'composer-2.5',
                choices: [{ delta: {}, index: 0, finish_reason: 'stop' }]
            };
            res.write(`data: ${JSON.stringify(finalChunk)}\n\n`);
            res.write(`data: [DONE]\n\n`);
            res.end();
        } else {
            // Non-streaming fallback
            let fullText = "";
            for await (const event of run.stream()) {
                if (event.type === 'TextDeltaUpdateSchema') {
                    fullText += event.delta;
                }
            }
            res.json({
                id: 'chatcmpl-cursor',
                object: 'chat.completion',
                created: Date.now(),
                model: model || 'composer-2.5',
                choices: [{
                    message: { role: 'assistant', content: fullText },
                    index: 0,
                    finish_reason: 'stop'
                }]
            });
        }
    } catch (error) {
        console.error("Cursor Proxy Error:", error);
        res.status(500).json({ error: error.message });
    }
});

const PORT = process.env.PORT || 8001;
app.listen(PORT, () => {
    console.log(`Cursor Proxy listening on port ${PORT}`);
});
