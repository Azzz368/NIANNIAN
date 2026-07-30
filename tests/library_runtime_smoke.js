const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync('frontend/library.html', 'utf8');
const script = fs.readFileSync('frontend/js/library.js', 'utf8');
const css = fs.readFileSync('frontend/css/library.css', 'utf8');
const ids = new Set(Array.from(html.matchAll(/id="([^"]+)"/g), match => match[1]));

class FakeElement {
  constructor(id = '') {
    this.id = id;
    this.style = {};
    this.dataset = {};
    this.children = [];
    this.listeners = {};
    this.classList = {
      add() {},
      remove() {},
      toggle() {},
      contains() { return false; },
    };
    this.value = '';
    this.textContent = '';
    this.disabled = false;
    this.options = [];
    this.selectedIndex = 0;
    this._innerHTML = '';
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    if (value === '') {
      this.children = [];
      this.options = [];
    }
  }

  get innerHTML() {
    return this._innerHTML;
  }

  appendChild(child) {
    this.children.push(child);
    if (this.id === 'libPersonSelect') this.options.push(child);
    return child;
  }

  addEventListener(type, handler) {
    (this.listeners[type] ||= []).push(handler);
  }

  querySelector() {
    return new FakeElement();
  }

  querySelectorAll() {
    return [];
  }

  contains() {
    return false;
  }
}

const elements = new Map(Array.from(ids, id => [id, new FakeElement(id)]));
global.window = global;
global.document = {
  getElementById(id) {
    return elements.get(id) || null;
  },
  createElement() {
    return new FakeElement();
  },
  querySelectorAll() {
    return [];
  },
  querySelector() {
    return null;
  },
  addEventListener() {},
};
global.location = { search: '', href: '' };
global.navigator = {};
global.alert = () => {};
global.confirm = () => true;

let activeMemorialId = 'person-a';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const jsonResponse = (value, wait = 0) => ({
  ok: true,
  status: 200,
  async json() {
    if (wait) await delay(wait);
    return value;
  },
});

global.NianAuth = {
  requireAuth: () => true,
  getUser: () => ({ display_name: '测试用户' }),
  logout() {},
  getActiveMemorialId: () => activeMemorialId,
  setActiveMemorialId: id => { activeMemorialId = id || ''; },
  async fetch(url) {
    if (url === '/api/memorials') {
      return jsonResponse({
        memorials: [
          { memorial_id: 'person-a', name: '人物 A', relation: '家人' },
          { memorial_id: 'person-b', name: '人物 B', relation: '朋友' },
        ],
      });
    }
    if (url.includes('/person-a/conversations')) {
      return jsonResponse({ conversations: [{ role: 'user', content: '只属于 A' }] }, 5);
    }
    if (url.includes('/person-b/conversations')) {
      return jsonResponse({ conversations: [{ role: 'user', content: '只属于 B' }] }, 5);
    }
    if (url === '/api/memorials/person-a') {
      return jsonResponse({
        meta: { memorial_id: 'person-a', name: '人物 A', relation: '家人' },
        dossier: {},
        assets: [{
          asset_id: 'image-a',
          kind: 'image',
          filename: '人物A照片.jpg',
          url: '/api/memorials/person-a/assets/image-a',
          user_description: '人物 A 正在接受采访',
          visual_summary: '一位戴眼镜的人手持麦克风',
          tags: ['采访', '麦克风'],
        }],
      }, 5);
    }
    if (url === '/api/memorials/person-b') {
      return jsonResponse({
        meta: { memorial_id: 'person-b', name: '人物 B', relation: '朋友' },
        dossier: {},
        assets: [],
      }, 50);
    }
    throw new Error(`Unexpected URL: ${url}`);
  },
};

vm.runInThisContext(script, { filename: 'frontend/js/library.js' });

(async () => {
  await delay(30);
  if (elements.get('detailBody').style.display !== 'block') {
    throw new Error('资料库详情没有显示，页面可能仍为空白');
  }
  if (elements.get('dName').textContent !== '人物 A') {
    throw new Error('初始人物资料加载错误');
  }

  const selector = elements.get('libPersonSelect');
  const change = selector.listeners.change && selector.listeners.change[0];
  if (!change) throw new Error('人物选择器没有绑定切换事件');

  selector.value = 'person-b';
  change();
  await delay(1);
  selector.value = 'person-a';
  change();
  await delay(90);

  if (elements.get('dName').textContent !== '人物 A') {
    throw new Error('迟到的旧人物响应覆盖了当前人物');
  }
  if (!elements.get('convList').innerHTML.includes('只属于 A')) {
    throw new Error('当前人物对话没有加载');
  }
  if (elements.get('convList').innerHTML.includes('只属于 B')) {
    throw new Error('上一人物对话混入当前人物');
  }

  const findByClass = (node, className) => {
    if ((node.className || '').split(/\s+/).includes(className)) return node;
    for (const child of node.children || []) {
      const found = findByClass(child, className);
      if (found) return found;
    }
    return null;
  };
  const imageCard = findByClass(elements.get('assetsGrouped'), 'asset-card-image');
  if (!imageCard) throw new Error('图片素材没有使用独立的纵向卡片布局');
  if (!imageCard.innerHTML.includes('asset-field-label') || !imageCard.innerHTML.includes('asset-field-value')) {
    throw new Error('素材描述没有使用可读的标签/正文结构');
  }
  if (imageCard.innerHTML.includes('asset-card-top')) {
    throw new Error('图片卡片仍错误复用了文件行的横向 Flex 容器');
  }
  if (
    !css.includes('.asset-card-image > .asset-card-body') ||
    !css.includes('.asset-card-image > .asset-card-body .asset-card-desc > .asset-field-value') ||
    !css.includes('display: block')
  ) {
    throw new Error('图片卡片 CSS 没有强制使用满宽块级正文布局');
  }
  if (!html.includes('AI 分析</strong>') || !html.includes('问念念</strong>')) {
    throw new Error('素材操作说明没有显示');
  }

  const uploadFlow = script.slice(
    script.indexOf('async function doLibUpload()'),
    script.indexOf('// ── 生成传记')
  );
  if (
    !uploadFlow.includes('setLibUploadBusy(false)') ||
    uploadFlow.includes('await selectMemorial(targetMid)') ||
    !uploadFlow.includes('state.assets.unshift(uploadedAsset)')
  ) {
    throw new Error('上传完成后仍可能被资料库刷新阻塞，或没有就地更新素材清单');
  }

  console.log('library runtime smoke: OK');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
