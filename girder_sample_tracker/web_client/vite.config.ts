import { resolve } from 'path';

import { defineConfig } from 'vite';
import istanbul from 'vite-plugin-istanbul';
import { compileClient } from 'pug';

function pugPlugin() {
  return {
    name: 'pug',
    transform(src: string, id: string) {
      if (id.endsWith('.pug')) {
        return {
          code: `${compileClient(src, {filename: id})}\nexport default template`,
          map: null,
        };
      }
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    pugPlugin(),
    istanbul({
      include: 'src/*',
      exclude: ['node_modules', 'test/'],
      extension: [ '.js', '.ts', '.vue' ],
      // requireEnv: true,
    }),
  ],
  optimizeDeps: {
     include: ["jquery"],
  },
  build: {
    sourcemap: true,
    lib: {
      entry: resolve(__dirname, 'main.js'),
      name: 'GirderPluginSampleTracker',
      fileName: 'girder-plugin-sample-tracker',
    },
    rollupOptions: {
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'style.css';
          }
          return '[name].[ext]';
        },
      },
      transform: {
        inject: {
          $: 'jquery',
          jQuery: 'jquery',
          'window.jQuery': 'jquery',
        },
      },
    },
  },
});
