const jwt = require('jsonwebtoken');

exports.protect = (roles = []) => (req, res, next) => {
  try {
    const authHeader = req.headers.authorization || req.get('Authorization');

    if (!authHeader) {
      return res.status(401).json({ message: 'Unauthorized: missing Authorization header' });
    }

    const parts = authHeader.split(' ');
    if (parts.length !== 2 || !/^Bearer$/i.test(parts[0])) {
      return res.status(401).json({ message: 'Unauthorized: malformed Authorization header' });
    }

    const token = parts[1]?.trim();
    if (!token) {
      return res.status(401).json({ message: 'Unauthorized: token missing' });
    }

    let decoded;
    try {
      decoded = jwt.verify(token, process.env.JWT_SECRET);
    } catch (err) {
      // Handle common JWT errors explicitly, respond with 401 for invalid/expired/malformed tokens
      if (err && (err.name === 'TokenExpiredError' || err.name === 'JsonWebTokenError' || err.name === 'NotBeforeError')) {
        const msg =
          err.name === 'TokenExpiredError'
            ? 'Unauthorized: token expired'
            : 'Unauthorized: invalid token';
        return res.status(401).json({ message: msg });
      }
      return res.status(401).json({ message: 'Unauthorized: token verification failed' });
    }

    // Attach decoded payload to req.user
    req.user = decoded;

    // Role-based access control (if roles are provided)
    if (Array.isArray(roles) && roles.length > 0) {
      const userRole = decoded && decoded.role;
      if (!roles.includes(userRole)) {
        return res.status(403).json({ message: 'Forbidden: insufficient permissions' });
      }
    }

    return next();
  } catch (e) {
    return res.status(500).json({ message: 'Internal server error' });
  }
};
