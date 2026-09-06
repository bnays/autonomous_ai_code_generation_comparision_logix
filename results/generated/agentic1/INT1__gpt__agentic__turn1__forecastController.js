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
 * Returns forecasts for all products under a given category.
 * Route: GET /api/inventory/forecast/category/:category_id
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

    // Resolve Paths to Python AI module
    const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
    const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

    try {
        // 1. Lookup products by category
        const [products] = await db.execute(
            'SELECT sku, product_name FROM products WHERE category_id = ?',
            [category_id]
        );

        // 2. If no products, return empty data set (no AI processes spawned)
        if (!products || products.length === 0) {
            return res.status(200).json({
                category_id,
                data: []
            });
        }

        // Helper to run forecast for a given SKU and return per-product result
        const runForecastForSku = (sku) => {
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

                pythonProcess.on('error', (err) => {
                    resolve({ error: `Failed to spawn AI process: ${err.message}` });
                });

                pythonProcess.on('close', (code) => {
                    if (code !== 0) {
                        console.error(`AI Engine Error for SKU ${sku} (Code ${code}):`, errorData);
                        return resolve({ error: `Forecasting engine error: ${errorData.trim()}` });
                    }
                    try {
                        const parsed = JSON.parse(rawData);
                        if (parsed && parsed.error) {
                            return resolve({ error: parsed.error });
                        }
                        resolve({ forecast: parsed });
                    } catch (e) {
                        resolve({ error: `Failed to parse AI output: ${e.message}` });
                    }
                });
            });
        };

        // 3. Run forecasts for all products concurrently
        const forecastPromises = products.map((p) =>
            runForecastForSku(p.sku).then((result) => {
                if (result && result.forecast) {
                    return {
                        sku: p.sku,
                        product_name: p.product_name,
                        forecast: result.forecast
                    };
                } else {
                    return {
                        sku: p.sku,
                        product_name: p.product_name,
                        error: result.error || 'Unknown forecasting error'
                    };
                }
            })
        );

        const results = await Promise.all(forecastPromises);

        // 4. Return aggregated results
        return res.status(200).json({
            category_id,
            data: results
        });
    } catch (dbError) {
        console.error("Database error in category forecast controller:", dbError.message);
        return res.status(500).json({ message: "Failed to query category products" });
    }
};
