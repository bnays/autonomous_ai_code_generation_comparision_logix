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
 * GET CATEGORY FORECAST
 * Runs the Python AI model for every product in a category and aggregates results.
 * GET /api/inventory/forecast/category/:category_id
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

    // Resolve paths the same way getProductForecast does
    const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
    const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

    // 1. Look up all products in the given category
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

    // 2. If no products match, return early with an empty data array
    if (products.length === 0) {
        return res.status(200).json({ category_id, data: [] });
    }

    /**
     * Helper: run forecast.py for a single SKU and resolve with either
     * { sku, product_name, forecast: {...} } or { sku, product_name, error: "..." }.
     * Never rejects, so Promise.all can collect every result regardless of failures.
     */
    const runForecastForProduct = ({ sku, product_name }) => {
        return new Promise((resolve) => {
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
                    console.error(
                        `AI Engine Error for SKU ${sku} (Code ${code}):`,
                        errorData
                    );
                    return resolve({
                        sku,
                        product_name,
                        error: `Forecasting engine exited with code ${code}: ${errorData}`.trim()
                    });
                }

                try {
                    const forecastResult = JSON.parse(rawData);

                    if (forecastResult.error) {
                        return resolve({
                            sku,
                            product_name,
                            error: forecastResult.error
                        });
                    }

                    resolve({
                        sku,
                        product_name,
                        forecast: forecastResult
                    });
                } catch (parseError) {
                    resolve({
                        sku,
                        product_name,
                        error: `Failed to parse AI output: ${parseError.message}`
                    });
                }
            });

            // Guard against the process itself failing to spawn
            pythonProcess.on('error', (spawnError) => {
                resolve({
                    sku,
                    product_name,
                    error: `Failed to spawn forecasting process: ${spawnError.message}`
                });
            });
        });
    };

    // 3. Run all forecasts concurrently and collect results
    const data = await Promise.all(products.map(runForecastForProduct));

    // 4. Return the aggregated payload
    return res.status(200).json({ category_id, data });
};
