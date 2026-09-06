const jwt = require('jsonwebtoken');

exports.protect = (roles = []) => {
  const allowedRoles = Array.isArray(roles) ? roles : [roles];

  return (req, res, next) => {
    // Get Authorization header safely (tests may not provide req.get)
    const authHeader =
      (typeof req.get === 'function' && req.get('Authorization')) ||
      (req.headers && (req.headers.authorization || req.headers.Authorization));

    if (!authHeader || typeof authHeader !== 'string') {
      return res.status(401).json({ message: 'Unauthorized: Missing Authorization header' });
    }

    // Validate Bearer format
    const parts = authHeader.split(' ');
    if (parts.length !== 2 || !/^Bearer$/i.test(parts[0])) {
      return res.status(401).json({ message: 'Unauthorized: Malformed Authorization header' });
    }

    const token = parts[1];
    if (!token) {
      return res.status(401).json({ message: 'Unauthorized: Missing token' });
    }

    // Verify token
    let decoded;
    try {
      decoded = jwt.verify(token, process.env.JWT_SECRET);
    } catch (err) {
      return res.status(401).json({ message: 'Unauthorized: Invalid or expired token' });
    }

    // Attach decoded payload
    req.user = decoded;

    // Role-based authorization if roles are specified
    if (allowedRoles.length > 0) {
      const userRole = decoded && (decoded.role ?? decoded.userRole ?? decoded.roles);
      if (!allowedRoles.includes(userRole)) {
        return res.status(403).json({ message: 'Forbidden: Insufficient permissions' });
      }
    }

    return next();
  };
};
