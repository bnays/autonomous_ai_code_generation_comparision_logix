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
 * Route: GET /api/inventory/forecast/category/:category_id
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

    // Resolve Paths to Python components
    const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
    const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

    try {
        // Look up all products in the given category
        const [products] = await db.execute(
            'SELECT sku, product_name FROM products WHERE category_id = ?',
            [category_id]
        );

        // If none match, return empty data without spawning forecasts
        if (!products || products.length === 0) {
            return res.status(200).json({ category_id, data: [] });
        }

        // For each product, run the forecasting script
        const forecastPromises = products.map(({ sku, product_name }) => {
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
                    // Failed to start the process
                    resolve({
                        sku,
                        product_name,
                        error: `Failed to start forecasting engine: ${err.message}`
                    });
                });

                pythonProcess.on('close', (code) => {
                    if (code !== 0) {
                        // Non-zero exit code from Python
                        return resolve({
                            sku,
                            product_name,
                            error: errorData || `Forecasting engine exited with code ${code}`
                        });
                    }

                    try {
                        const forecastResult = JSON.parse(rawData);

                        if (forecastResult && forecastResult.error) {
                            resolve({ sku, product_name, error: forecastResult.error });
                        } else {
                            resolve({ sku, product_name, forecast: forecastResult });
                        }
                    } catch (parseError) {
                        resolve({
                            sku,
                            product_name,
                            error: `Failed to parse AI output: ${parseError.message}`
                        });
                    }
                });
            });
        });

        const results = await Promise.all(forecastPromises);

        return res.status(200).json({
            category_id,
            data: results
        });
    } catch (dbError) {
        console.error("Database error in category forecast controller:", dbError.message);
        return res.status(500).json({ message: "Failed to query category products" });
    }
};
