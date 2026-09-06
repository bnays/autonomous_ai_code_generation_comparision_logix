const jwt = require('jsonwebtoken');

exports.protect = (roles = []) => (req, res, next) => {
  try {
    const authHeader = req.headers.authorization || req.headers.Authorization;

    if (!authHeader) {
      return res.status(401).json({ message: 'Missing Authorization header' });
    }

    const parts = String(authHeader).trim().split(/\s+/);
    if (parts.length !== 2 || !/^Bearer$/i.test(parts[0])) {
      return res.status(401).json({ message: 'Invalid Authorization header format' });
    }

    const token = parts[1];
    if (!token) {
      return res.status(401).json({ message: 'Missing token' });
    }

    let decoded;
    try {
      decoded = jwt.verify(token, process.env.JWT_SECRET);
    } catch (err) {
      if (err && err.name === 'TokenExpiredError') {
        return res.status(401).json({ message: 'Token expired' });
      }
      return res.status(401).json({ message: 'Invalid token' });
    }

    req.user = decoded;

    if (Array.isArray(roles) && roles.length > 0) {
      const userRole = decoded.role ?? decoded.roles;

      let isAllowed = false;
      if (Array.isArray(userRole)) {
        isAllowed = userRole.some((r) => roles.includes(r));
      } else {
        isAllowed = roles.includes(userRole);
      }

      if (!isAllowed) {
        return res.status(403).json({ message: 'Forbidden' });
      }
    }

    return next();
  } catch (e) {
    return res.status(401).json({ message: 'Not authorized' });
  }
};
