// File: backend/controllers/forecastController.js
const { spawn } = require('child_process');
const path = require('path');
const db = require('../config/db');

/**
 * GET PRODUCT FORECAST
 * Triggers the Python AI model and returns predictive aggregates.
 */
exports.getProductForecast = async (req, res) => {
    const { sku } = req.params;

    // 1. Resolve Paths
    // Paths are relative to this file: controllers -> backend -> project-root
    const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
    const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

    try {
        // 2. Fetch Product metadata from live MySQL
        const [product] = await db.execute(
            'SELECT product_name FROM products WHERE sku = ?',
            [sku]
        );

        if (product.length === 0) {
            return res.status(404).json({ message: `SKU ${sku} not found in database.` });
        }

        const productName = product[0].product_name;

        // 3. Spawn Python Child Process
        // We pass process.env so Python can see the DB_PASS and DB_USER
        const pythonProcess = spawn(pythonExecutable, [pythonScript, sku], {
            env: { ...process.env }
        });

        let rawData = '';
        let errorData = '';

        // 4. Listen for Data
        pythonProcess.stdout.on('data', (data) => {
            rawData += data.toString();
        });

        pythonProcess.stderr.on('data', (data) => {
            errorData += data.toString();
        });

        // 5. Handle Process Completion
        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                console.error(`AI Engine Error (Code ${code}):`, errorData);
                return res.status(500).json({
                    message: "Forecasting engine error",
                    details: errorData
                });
            }

            try {
                // Parse the JSON string sent by Python's print(json.dumps())
                const forecastResult = JSON.parse(rawData);

                if (forecastResult.error) {
                    return res.status(400).json({ message: forecastResult.error });
                }

                // Return enriched payload for the dashboard
                res.status(200).json({
                    ...forecastResult,
                    productName,
                    generatedAt: new Date().toISOString()
                });
            } catch (parseError) {
                res.status(500).json({
                    message: "Failed to parse AI output",
                    details: parseError.message
                });
            }
        });

    } catch (dbError) {
        console.error("Database error in forecast controller:", dbError.message);
        res.status(500).json({ message: "Failed to query product information" });
    }
};

/**
 * Helper: Run forecast.py for a single SKU and return a Promise that resolves
 * with the parsed forecast result, or rejects with an error message string.
 */
function runForecastForSku(sku) {
    return new Promise((resolve, reject) => {
        const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
        const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

        const pythonProcess = spawn(pythonExecutable, [pythonScript, sku], {
            env: { ...process.env }
        });

        let rawData = '';
        let errorData = '';

        pythonProcess.stdout.on('data', (data) => {
            rawData += data.toString();
        });

        pythonProcess.stderr.on('data', (data) => {
            errorData += data.toString();
        });

        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                return reject(
                    `AI Engine Error (Code ${code}): ${errorData.trim()}`
                );
            }

            try {
                const forecastResult = JSON.parse(rawData);

                if (forecastResult.error) {
                    return reject(forecastResult.error);
                }

                resolve(forecastResult);
            } catch (parseError) {
                reject(`Failed to parse AI output: ${parseError.message}`);
            }
        });

        pythonProcess.on('error', (spawnError) => {
            reject(`Failed to spawn forecast process: ${spawnError.message}`);
        });
    });
}

/**
 * GET CATEGORY FORECAST
 * Runs the Python AI model for every product in a category and aggregates results.
 * Route: GET /api/inventory/forecast/category/:category_id
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

    // 1. Fetch all products belonging to this category
    let products;
    try {
        const [rows] = await db.execute(
            'SELECT sku, product_name FROM products WHERE category_id = ?',
            [category_id]
        );
        products = rows;
    } catch (dbError) {
        console.error("Database error in getCategoryForecast:", dbError.message);
        return res.status(500).json({ message: "Failed to query category products" });
    }

    // 2. If no products found, return empty data without spawning anything
    if (products.length === 0) {
        return res.status(200).json({ category_id, data: [] });
    }

    // 3. Run forecasts concurrently for all products; capture per-product failures
    const forecastPromises = products.map(async ({ sku, product_name }) => {
        try {
            const forecast = await runForecastForSku(sku);
            return { sku, product_name, forecast };
        } catch (forecastError) {
            console.error(
                `Forecast failed for SKU ${sku} (category ${category_id}):`,
                forecastError
            );
            return { sku, product_name, error: String(forecastError) };
        }
    });

    const data = await Promise.all(forecastPromises);

    // 4. Return aggregated results
    return res.status(200).json({ category_id, data });
};
