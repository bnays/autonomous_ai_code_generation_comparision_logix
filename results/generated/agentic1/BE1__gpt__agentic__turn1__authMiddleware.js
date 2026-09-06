const jwt = require('jsonwebtoken');

exports.protect = (roles = []) => {
  const allowedRoles = Array.isArray(roles) ? roles : [roles];

  return (req, res, next) => {
    try {
      const authHeader = req.get('Authorization') || req.headers.authorization;

      if (!authHeader || typeof authHeader !== 'string' || !authHeader.toLowerCase().startsWith('bearer ')) {
        return res.status(401).json({ message: 'Unauthorized: Missing or invalid Authorization header' });
      }

      const token = authHeader.split(' ')[1];
      if (!token) {
        return res.status(401).json({ message: 'Unauthorized: Missing token' });
      }

      let decoded;
      try {
        decoded = jwt.verify(token, process.env.JWT_SECRET);
      } catch (err) {
        return res.status(401).json({ message: 'Unauthorized: Invalid or expired token' });
      }

      req.user = decoded;

      if (allowedRoles.length > 0) {
        const userRole = decoded && (decoded.role || decoded.roles || decoded.userRole);
        if (!allowedRoles.includes(userRole)) {
          return res.status(403).json({ message: 'Forbidden: Insufficient permissions' });
        }
      }

      return next();
    } catch (err) {
      return res.status(401).json({ message: 'Unauthorized' });
    }
  };
};
