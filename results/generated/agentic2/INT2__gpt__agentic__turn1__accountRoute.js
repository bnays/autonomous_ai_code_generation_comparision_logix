// backend/routes/accountRoute.js
const express = require('express');
const { protect } = require('../middleware/authMiddleware');

const router = express.Router();

router.get('/session', protect(['admin', 'user']), (req, res) => {
  return res.status(200).json({ user: req.user });
});

module.exports = router;
