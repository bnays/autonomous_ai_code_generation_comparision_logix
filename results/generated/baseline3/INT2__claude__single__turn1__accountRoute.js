// routes/accountRoute.js
const express = require('express');
const router = express.Router();
const { protect } = require('../middleware/authMiddleware');

router.get('/session', protect(['admin', 'user']), (req, res) => {
    return res.status(200).json({ user: req.user });
});

module.exports = router;
