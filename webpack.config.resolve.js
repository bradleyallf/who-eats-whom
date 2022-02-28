const path = require('path');

// https://github.com/electron-react-boilerplate/electron-react-boilerplate/issues/1321#issuecomment-349767539
module.exports = {
  resolve: {
    alias: {
      $common: path.resolve(__dirname, 'src/common/'),
      $components: path.resolve(__dirname, 'src/components/'),
      $hooks: path.resolve(__dirname, 'src/hooks/'),
      $images: path.resolve(__dirname, 'src/assets/images/'),
      $models: path.resolve(__dirname, 'src/models/'),
      $route: path.resolve(__dirname, 'src/route/'),
      $screens: path.resolve(__dirname, 'src/screens/'),
      $scss: path.resolve(__dirname, 'src/scss/'),
    },
    extensions: ['*', '.js', '.json', '.jsx'],
  },
};
