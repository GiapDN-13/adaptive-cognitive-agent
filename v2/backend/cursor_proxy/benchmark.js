const { Agent } = require('@cursor/sdk');
const apiKey = process.env.CURSOR_API_KEY;  // set via env / v2/.env — never hardcode
if (!apiKey) { console.error('CURSOR_API_KEY not set'); process.exit(1); }

const modelsToTest = [
    'composer-2.5',
    'claude-sonnet-4-6',
    'gpt-5.3-codex',
    'claude-haiku-4-5'
];

const prompt = "Write a one-sentence greeting in Vietnamese.";

async function runBenchmark() {
    console.log("Starting Cursor Models Benchmark...\n");
    console.log(String().padEnd(65, '-'));
    console.log(
        "Model".padEnd(25) + 
        "| TTFT (ms)".padEnd(15) + 
        "| Total Time (ms)".padEnd(20) + 
        "| Status"
    );
    console.log(String().padEnd(65, '-'));

    for (const model of modelsToTest) {
        try {
            const agent = await Agent.create({
                apiKey: apiKey,
                model: { id: model }
            });

            const startTime = Date.now();
            let firstTokenTime = null;

            const run = await agent.send(prompt);
            
            for await (const event of run.stream()) {
                if (!firstTokenTime && event.type === 'TextDeltaUpdateSchema') {
                    firstTokenTime = Date.now();
                }
            }

            const endTime = Date.now();
            const ttft = firstTokenTime ? (firstTokenTime - startTime) : 0;
            const total = endTime - startTime;

            console.log(
                model.padEnd(25) + 
                `| ${ttft.toString().padEnd(13)}` + 
                `| ${total.toString().padEnd(18)}` + 
                "| OK"
            );
        } catch (error) {
            console.log(
                model.padEnd(25) + 
                "| N/A".padEnd(14) + 
                "| N/A".padEnd(19) + 
                "| ERROR: " + error.message.split('\n')[0]
            );
        }
    }
    console.log(String().padEnd(65, '-'));
}

runBenchmark();
