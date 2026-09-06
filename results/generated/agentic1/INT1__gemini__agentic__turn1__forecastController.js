const { spawn } = require('child_process');
const path = require('path');
const db = require('../config/db');

// Paths relative to this file: controllers -> backend -> project-root
const pythonScript = path.resolve(__dirname, '../../ai-module/forecast.py');
const pythonExecutable = path.resolve(__dirname, '../../ai-module/venv/bin/python3');

/**
 * Helper to run the Python forecast process for a single SKU.
 */
const runSingleForecast = (sku, productName) => {
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
                return resolve({
                    sku,
                    product_name: productName,
                    error: errorData || `Forecasting engine error (code ${code})`
                });
            }

            try {
                const forecastResult = JSON.parse(rawData);

                if (forecastResult.error) {
                    return resolve({
                        sku,
                        product_name: productName,
                        error: forecastResult.error
                    });
                }

                return resolve({
                    sku,
                    product_name: productName,
                    forecast: forecastResult
                });
            } catch (parseError) {
                return resolve({
                    sku,
                    product_name: productName,
                    error: parseError.message || "Failed to parse AI output"
                });
            }
        });

        pythonProcess.on('error', (err) => {
            return resolve({
                sku,
                product_name: productName,
                error: err.message
            });
        });
    });
};

/**
 * GET PRODUCT FORECAST
 * Triggers the Python AI model and returns predictive aggregates for a single product.
 */
exports.getProductForecast = async (req, res) => {
    const { sku } = req.params;

    try {
        // Fetch Product metadata from live MySQL
        const [product] = await db.execute(
            'SELECT product_name FROM products WHERE sku = ?',
            [sku]
        );

        if (product.length === 0) {
            return res.status(404).json({ message: `SKU ${sku} not found in database.` });
        }

        const productName = product[0].product_name;

        // Spawn Python Child Process
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
                console.error(`AI Engine Error (Code ${code}):`, errorData);
                return res.status(500).json({
                    message: "Forecasting engine error",
                    details: errorData
                });
            }

            try {
                const forecastResult = JSON.parse(rawData);

                if (forecastResult.error) {
                    return res.status(400).json({ message: forecastResult.error });
                }

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
 * Look up all products in a category and run forecasts for each.
 */
exports.getCategoryForecast = async (req, res) => {
    const { category_id } = req.params;

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

        const forecastPromises = products.map((product) =>
            runSingleForecast(product.sku, product.product_name)
        );

        const data = await Promise.all(forecastPromises);

        return res.status(200).json({
            category_id,
            data
        });
    } catch (dbError) {
        console.error("Database error in category forecast controller:", dbError.message);
        return res.status(500).json({ message: "Failed to query category products" });
    }
};
