// backend/routes/accountRoute.js
const express = require('express');
const router = express.Router();
const { protect } = require('../middleware/authMiddleware');

router.get('/session', protect(['admin', 'user']), (req, res) => {
    res.status(200).json({ user: req.user });
});

module.exports = router;
