const db = require('../config/db');

/**
 * FETCH ALL INVENTORY
 * Uses a LEFT JOIN to combine Product details with current Stock levels.
 */
exports.getAllInventory = async (req, res) => {
    try {
        const { page = 1, limit = 10, search = '' } = req.query;
        const offset = (page - 1) * limit;
        const searchVal = `%${search}%`;

        const [countResult] = await db.execute(
            'SELECT COUNT(*) as total FROM products WHERE product_name LIKE ? OR sku LIKE ?',
            [searchVal, searchVal]
        );
        const totalItems = countResult[0].total;

        const query = `
            SELECT 
                p.*, 
                IFNULL(i.quantity_on_hand, 0) as quantity_on_hand, 
                c.name AS category 
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.product_name LIKE ? OR p.sku LIKE ?
            ORDER BY p.product_id DESC 
            LIMIT ? OFFSET ?
        `;

        const [rows] = await db.execute(query, [searchVal, searchVal, String(limit), String(offset)]);

        res.status(200).json({
            data: rows,
            meta: {
                totalItems,
                currentPage: Number(page)
            }
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

/**
 * CREATE PRODUCT & INITIALIZE STOCK
 * Uses a Transaction to ensure data integrity across tables.
 */
exports.createProduct = async (req, res) => {
    const {
        product_name, sku, category_id, unit_price, reorder_level, initial_stock, suppliers
    } = req.body;

    const connection = await db.getConnection();

    try {
        await connection.beginTransaction();

        const productSql = `
            INSERT INTO products (product_name, sku, category_id, unit_price, reorder_level) 
            VALUES (?, ?, ?, ?, ?)
        `;
        const [productResult] = await connection.execute(productSql, [
            product_name, sku, category_id, unit_price, reorder_level
        ]);

        const newProductId = productResult.insertId;

        // Initialize inventory levels
        await connection.execute(
            'INSERT INTO inventory (product_id, quantity_on_hand) VALUES (?, ?)',
            [newProductId, initial_stock || 0]
        );

        if (suppliers && suppliers.length > 0) {
            const supplierSql = `
                INSERT INTO product_suppliers (product_id, supplier_id, supply_price, lead_time_days) 
                VALUES (?, ?, ?, ?)
            `;
            const supplierPromises = suppliers.map(sup =>
                connection.execute(supplierSql, [
                    newProductId, sup.supplier_id, sup.supply_price || unit_price, sup.lead_time_days || 7
                ])
            );
            await Promise.all(supplierPromises);
        }

        await connection.commit();
        res.status(201).json({ message: "Product created and inventory initialized.", productId: newProductId });

    } catch (error) {
        await connection.rollback();
        res.status(500).json({ message: "Failed to create product", error: error.message });
    } finally {
        connection.release();
    }
};

/**
 * UPDATE STOCK LEVEL (Adjustment)
 * FIXED: Now uses an "Upsert" logic to handle missing inventory rows.
 */
exports.updateStock = async (req, res) => {
    const { id } = req.params; // product_id
    const { quantity_change } = req.body;

    try {
        // Attempt update first
        const [updateResult] = await db.execute(
            'UPDATE inventory SET quantity_on_hand = quantity_on_hand + ? WHERE product_id = ?',
            [quantity_change, id]
        );

        // If no row existed, create it now (Safety Fix for STR-024 issue)
        if (updateResult.affectedRows === 0) {
            await db.execute(
                'INSERT INTO inventory (product_id, quantity_on_hand) VALUES (?, ?)',
                [id, quantity_change]
            );
        }

        res.status(200).json({ message: "Stock synchronized successfully" });
    } catch (error) {
        res.status(500).json({ message: "Error updating stock", error: error.message });
    }
};

/**
 * UPDATE PRODUCT
 * Synchronizes core details and Many-to-Many Supplier links.
 */
exports.updateProduct = async (req, res) => {
    const { id } = req.params;
    const { product_name, sku, category_id, unit_price, reorder_level, suppliers } = req.body;

    const connection = await db.getConnection();

    try {
        await connection.beginTransaction();

        await connection.execute(
            `UPDATE products SET product_name = ?, sku = ?, category_id = ?, unit_price = ?, reorder_level = ? 
             WHERE product_id = ?`,
            [product_name, sku, category_id, unit_price, reorder_level, id]
        );

        if (suppliers) {
            await connection.execute('DELETE FROM product_suppliers WHERE product_id = ?', [id]);
            if (suppliers.length > 0) {
                const supplierSql = 'INSERT INTO product_suppliers (product_id, supplier_id, supply_price) VALUES (?, ?, ?)';
                const supplierPromises = suppliers.map(sup =>
                    connection.execute(supplierSql, [id, sup.supplier_id, sup.supply_price])
                );
                await Promise.all(supplierPromises);
            }
        }

        await connection.commit();
        res.status(200).json({ message: "Product details and supplier links updated." });

    } catch (error) {
        await connection.rollback();
        res.status(500).json({ message: "Error updating product", error: error.message });
    } finally {
        connection.release();
    }
};

/**
 * DELETE PRODUCT
 * Deletes child inventory records before the parent product.
 */
exports.deleteProduct = async (req, res) => {
    const { id } = req.params;
    const connection = await db.getConnection();

    try {
        await connection.beginTransaction();
        await connection.execute('DELETE FROM inventory WHERE product_id = ?', [id]);
        await connection.execute('DELETE FROM products WHERE product_id = ?', [id]);
        await connection.commit();
        res.status(200).json({ message: "Product and stock records deleted." });
    } catch (error) {
        await connection.rollback();
        res.status(500).json({ message: "Error deleting product", error: error.message });
    } finally {
        connection.release();
    }
};

/**
 * GET LOW STOCK REPORT
 * Identifies products below reorder_level and suggests restock amounts.
 */
exports.getLowStockSuggestions = async (req, res) => {
    try {
        const query = `
            SELECT 
                p.product_id,
                p.product_name,
                p.sku,
                IFNULL(i.quantity_on_hand, 0) as quantity_on_hand,
                p.reorder_level,
                (p.reorder_level * 2 - IFNULL(i.quantity_on_hand, 0)) as suggested_restock_qty,
                IFNULL(s.name, 'No Supplier Assigned') as preferred_supplier,
                s.id as supplier_id,
                IFNULL(ps.supply_price, p.unit_price) as supply_price,
                (SELECT COUNT(*) 
                 FROM purchase_order_items poi 
                 JOIN purchase_orders po ON poi.purchase_id = po.id 
                 WHERE poi.product_id = p.product_id AND po.status = 'Pending'
                ) as pending_order_count
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id
            -- Double LEFT JOIN to ensure products show even without links
            LEFT JOIN product_suppliers ps ON ps.product_id = p.product_id
            LEFT JOIN suppliers s ON ps.supplier_id = s.id
            WHERE IFNULL(i.quantity_on_hand, 0) <= p.reorder_level
              AND (ps.supply_price IS NULL OR ps.supply_price = (
                  SELECT MIN(supply_price) 
                  FROM product_suppliers 
                  WHERE product_id = p.product_id
              ))
            GROUP BY 
                p.product_id, p.product_name, p.sku, i.quantity_on_hand, 
                p.reorder_level, s.name, s.id, ps.supply_price
            ORDER BY (p.reorder_level - IFNULL(i.quantity_on_hand, 0)) DESC;
        `;

        const [rows] = await db.execute(query);
        res.status(200).json({ success: true, data: rows });
    } catch (error) {
        res.status(500).json({ message: "Error generating report", error: error.message });
    }
};

/**
 * GET STOCK LEDGER
 * Provides an audit trail of all manual and automated adjustments.
 */
exports.getStockLedger = async (req, res) => {
    const { product_id, startDate, endDate } = req.query;
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const offset = (page - 1) * limit;

    let whereClause = "WHERE 1=1";
    const params = [];

    if (product_id) { whereClause += ` AND st.product_id = ?`; params.push(product_id); }
    if (startDate && endDate) {
        whereClause += ` AND st.created_at BETWEEN ? AND ?`;
        params.push(`${startDate} 00:00:00`, `${endDate} 23:59:59`);
    }

    try {
        const [countResult] = await db.execute(`SELECT COUNT(*) as total FROM stock_transactions st ${whereClause}`, params);
        const dataQuery = `
            SELECT st.*, p.product_name, p.sku, CONCAT(u.first_name, ' ', u.last_name) AS staff_member
            FROM stock_transactions st
            JOIN products p ON st.product_id = p.product_id
            JOIN users u ON st.user_id = u.user_id
            ${whereClause} ORDER BY st.created_at DESC LIMIT ? OFFSET ?
        `;
        const [rows] = await db.execute(dataQuery, [...params, String(limit), String(offset)]);
        res.status(200).json({ data: rows, total: countResult[0].total });
    } catch (error) {
        res.status(500).json({ message: "Stock Ledger synchronization failed", error: error.message });
    }
};

/**
 * GET PRODUCTS BY FILTER
 * Filters products by category, price range, and/or search term with pagination.
 */
exports.getProductsByFilter = async (req, res) => {
    try {
        const {
            category_id,
            min_price,
            max_price,
            search,
            page = 1,
            limit = 10
        } = req.query;

        const currentPage = parseInt(page, 10) || 1;
        const pageLimit = parseInt(limit, 10) || 10;
        const offset = (currentPage - 1) * pageLimit;

        const conditions = [];
        const countParams = [];

        if (category_id !== undefined && category_id !== '') {
            conditions.push('p.category_id = ?');
            countParams.push(category_id);
        }

        if (min_price !== undefined && min_price !== '') {
            conditions.push('p.unit_price >= ?');
            countParams.push(min_price);
        }

        if (max_price !== undefined && max_price !== '') {
            conditions.push('p.unit_price <= ?');
            countParams.push(max_price);
        }

        if (search !== undefined && search !== '') {
            const searchVal = `%${search}%`;
            conditions.push('(p.product_name LIKE ? OR p.sku LIKE ?)');
            countParams.push(searchVal, searchVal);
        }

        const whereClause = conditions.length > 0
            ? 'WHERE ' + conditions.join(' AND ')
            : '';

        const countSql = `
            SELECT COUNT(*) as total
            FROM products p
            ${whereClause}
        `;

        const [countResult] = await db.execute(countSql, countParams);
        const totalItems = countResult[0].total;

        const dataParams = [...countParams, String(pageLimit), String(offset)];

        const dataSql = `
            SELECT 
                p.*,
                IFNULL(i.quantity_on_hand, 0) as quantity_on_hand,
                c.name AS category
            FROM products p
            LEFT JOIN inventory i ON p.product_id = i.product_id
            LEFT JOIN categories c ON p.category_id = c.id
            ${whereClause}
            ORDER BY p.product_id DESC
            LIMIT ? OFFSET ?
        `;

        const [rows] = await db.execute(dataSql, dataParams);

        res.status(200).json({
            data: rows,
            meta: {
                totalItems,
                currentPage
            }
        });
    } catch (error) {
        res.status(500).json({ message: "Error filtering products", error: error.message });
    }
};
