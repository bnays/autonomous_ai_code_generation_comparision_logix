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
 * For a given category_id, runs the AI forecast for each product in the category.
 * Returns an array of results, each either with forecast data or an error.
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

    // Resolve Paths
    const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
    const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

    try {
        // Lookup all products in the category
        const [products] = await db.execute(
            'SELECT sku, product_name FROM products WHERE category_id = ?',
            [category_id]
        );

        if (!products || products.length === 0) {
            return res.status(200).json({ category_id, data: [] });
        }

        // For each product, spawn the forecast process and collect results
        const tasks = products.map((p) => new Promise((resolve) => {
            const pythonProcess = spawn(pythonExecutable, [pythonScript, p.sku], {
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
                // Failed to start process
                return resolve({
                    sku: p.sku,
                    product_name: p.product_name,
                    error: `Failed to start forecasting engine: ${err.message}`
                });
            });

            pythonProcess.on('close', (code) => {
                if (code !== 0) {
                    console.error(`AI Engine Error for SKU ${p.sku} (Code ${code}):`, errorData);
                    return resolve({
                        sku: p.sku,
                        product_name: p.product_name,
                        error: `Forecasting engine error (code ${code}): ${errorData}`
                    });
                }

                try {
                    const forecastResult = JSON.parse(rawData);

                    if (forecastResult.error) {
                        return resolve({
                            sku: p.sku,
                            product_name: p.product_name,
                            error: forecastResult.error
                        });
                    }

                    return resolve({
                        sku: p.sku,
                        product_name: p.product_name,
                        forecast: forecastResult
                    });
                } catch (parseError) {
                    return resolve({
                        sku: p.sku,
                        product_name: p.product_name,
                        error: `Failed to parse AI output: ${parseError.message}`
                    });
                }
            });
        }));

        const results = await Promise.all(tasks);

        return res.status(200).json({
            category_id,
            data: results
        });
    } catch (dbError) {
        console.error("Database error in category forecast controller:", dbError.message);
        return res.status(500).json({ message: "Failed to query category products" });
    }
};
