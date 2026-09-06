const { spawn } = require('child_process');
const path = require('path');
const db = require('../config/db');

/**
 * Helper function to run forecast script for a given SKU
 */
const runForecastForSku = (pythonExecutable, pythonScript, sku) => {
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
                return resolve({ error: errorData || `Process exited with code ${code}` });
            }

            try {
                const forecastResult = JSON.parse(rawData);
                if (forecastResult.error) {
                    return resolve({ error: forecastResult.error });
                }
                return resolve({ forecast: forecastResult });
            } catch (parseError) {
                return resolve({ error: parseError.message });
            }
        });

        pythonProcess.on('error', (err) => {
            return resolve({ error: err.message });
        });
    });
};

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
 * Triggers the Python AI model for all products in a category and returns batch forecast results.
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

    const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
    const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

    try {
        const [products] = await db.execute(
            'SELECT sku, product_name FROM products WHERE category_id = ?',
            [category_id]
        );

        if (products.length === 0) {
            return res.status(200).json({
                category_id,
                data: []
            });
        }

        const data = await Promise.all(
            products.map(async (product) => {
                const { sku, product_name } = product;
                const result = await runForecastForSku(pythonExecutable, pythonScript, sku);

                if (result.error) {
                    return {
                        sku,
                        product_name,
                        error: result.error
                    };
                }

                return {
                    sku,
                    product_name,
                    forecast: result.forecast
                };
            })
        );

        return res.status(200).json({
            category_id,
            data
        });
    } catch (dbError) {
        console.error("Database error in category forecast controller:", dbError.message);
        return res.status(500).json({ message: "Failed to query category products" });
    }
};
