const db = require('../config/db');

// Get all categories with product counts

exports.getAllCategories = async (req, res) => {
    try {
        const query = `
            SELECT 
                c.id, 
                c.name, 
                c.slug, 
                c.description, 
                c.created_at, 
                COUNT(p.product_id) AS product_count 
            FROM categories c 
            LEFT JOIN products p ON c.id = p.category_id 
            GROUP BY c.id, c.name, c.slug, c.description, c.created_at
            ORDER BY c.name ASC
        `;
        const [rows] = await db.execute(query);
        res.status(200).json(rows);
    } catch (error) {
        // This will log the error details in your terminal if it fails again
        console.error('SQL Error:', error.message);
        res.status(500).json({ message: "Error fetching categories", error: error.message });
    }
};

// Helper function to generate slugs
const slugify = (text) => {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replace(/\s+/g, '-')     // Replace spaces with -
        .replace(/[^\w-]+/g, '')   // Remove non-word characters
        .replace(/--+/g, '-');    // Replace multiple hyphens
};

// Add a new category
exports.createCategory = async (req, res) => {
    const { name, description } = req.body;

    // Generate slug from the name provided by the user
    const slug = slugify(name);
    try {
        const [result] = await db.execute(
            'INSERT INTO categories (name, description, slug) VALUES (?, ?, ?)',
            [name, description, slug]
        );
        res.status(201).json({ message: "Category created", id: result.insertId });
    } catch (error) {
        res.status(500).json({ message: "Error creating category", error: error.message });
    }
};


exports.updateCategory = async (req, res) => {
    const { id } = req.params;
    const { name, description = null } = req.body;

    // Generate a new slug based on the updated name
    const slug = name ? name.toLowerCase().replace(/ /g, '-').replace(/[^\w-]+/g, '') : null;

    try {
        const [result] = await db.execute(
            'UPDATE categories SET name = ?, description = ?, slug = ? WHERE id = ?',
            [name, description, slug, id]
        );

        if (result.affectedRows === 0) {
            return res.status(404).json({ message: "Category not found" });
        }

        res.status(200).json({ message: "Category updated successfully" });
    } catch (error) {
        if (error.code === 'ER_DUP_ENTRY') {
            return res.status(400).json({ message: "A category with this name already exists" });
        }
        res.status(500).json({ message: "Error updating category", error: error.message });
    }
};

// controllers/categoryController.js

exports.deleteCategory = async (req, res) => {
    const { id } = req.params;

    try {
        // Check if any products are still linked to this category
        const [products] = await db.execute(
            'SELECT product_id FROM products WHERE category_id = ? LIMIT 1',
            [id]
        );

        if (products.length > 0) {
            return res.status(400).json({
                message: "Cannot delete: This category still contains products."
            });
        }

        const [result] = await db.execute('DELETE FROM categories WHERE id = ?', [id]);

        if (result.affectedRows === 0) {
            return res.status(404).json({ message: "Category not found" });
        }

        res.status(200).json({ message: "Category deleted successfully" });
    } catch (error) {
        res.status(500).json({ message: "Error deleting category", error: error.message });
    }
};

// Get category sales report (total revenue and units sold per category)
exports.getCategorySalesReport = async (req, res) => {
    try {
        const query = `
            SELECT
                c.id,
                c.name,
                c.slug,
                c.description,
                c.created_at,
                COALESCE(SUM(soi.quantity * soi.unit_price), 0) AS total_revenue,
                COALESCE(SUM(soi.quantity), 0) AS total_units_sold
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id
            LEFT JOIN sale_order_items soi ON p.product_id = soi.product_id
            GROUP BY c.id, c.name, c.slug, c.description, c.created_at
            ORDER BY c.name ASC
        `;
        const [rows] = await db.execute(query);
        res.status(200).json(rows);
    } catch (error) {
        console.error('SQL Error:', error.message);
        res.status(500).json({ message: "Error fetching category sales report", error: error.message });
    }
};
