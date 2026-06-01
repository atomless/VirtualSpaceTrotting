import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      pages: '../dist/site',
      assets: '../dist/site',
      strict: true
    }),
    prerender: {
      crawl: true,
      entries: ['*']
    },
    env: {
      dir: '..',
      publicPrefix: 'BOOMERANG_'
    }
  }
};

export default config;
