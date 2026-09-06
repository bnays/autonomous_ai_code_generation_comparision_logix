const jwt = require('jsonwebtoken');

exports.protect = (roles = []) => {
  // Normalize roles to an array
  const allowedRoles = Array.isArray(roles) ? roles : [roles];

  return (req, res, next) => {
    try {
      const authHeader = req.headers?.authorization || req.headers?.Authorization;
      if (!authHeader) {
        return res.status(401).json({ message: 'Authorization header missing' });
      }

      const parts = authHeader.split(' ');
      if (parts.length !== 2 || !/^Bearer$/i.test(parts[0])) {
        return res.status(401).json({ message: 'Invalid authorization header format' });
      }

      const token = parts[1];
      if (!token) {
        return res.status(401).json({ message: 'Token missing' });
      }

      let decoded;
      try {
        const secret = process.env.JWT_SECRET;
        decoded = jwt.verify(token, secret);
      } catch (err) {
        // Covers malformed, invalid signature, and expired tokens
        return res.status(401).json({ message: 'Invalid or expired token' });
      }

      // Attach decoded payload to req.user
      req.user = decoded;

      // Role-based authorization if roles are provided
      if (allowedRoles.length > 0) {
        const userRole =
          (req.user && req.user.role) ||
          (req.user && req.user.user && req.user.user.role) ||
          null;

        if (!userRole || !allowedRoles.includes(userRole)) {
          return res.status(403).json({ message: 'Forbidden: insufficient role' });
        }
      }

      return next();
    } catch (err) {
      // Fallback for any unexpected errors
      return res.status(401).json({ message: 'Not authorized' });
    }
  };
};
