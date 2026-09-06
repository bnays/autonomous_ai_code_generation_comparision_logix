const express = require('express');
const { protect } = require('../middleware/authMiddleware');

const router = express.Router();

router.get('/session', protect(['admin', 'user']), (req, res) => {
    res.status(200).json({ user: req.user });
});

module.exports = router;
