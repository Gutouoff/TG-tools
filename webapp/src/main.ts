import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';

// @material/web 组件(按需引入)
import '@material/web/button/filled-button.js';
import '@material/web/button/outlined-button.js';
import '@material/web/textfield/filled-text-field.js';
import '@material/web/icon/icon.js';
import '@material/web/list/list.js';
import '@material/web/list/list-item.js';

const app = mount(App, {
  target: document.getElementById('app')!,
});

export default app;
