/**
 * 念念传记写作功能，改为三步式界面，模仿追思影像建档样式
 */

(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);

    const state = {
        step: 1,
        currentMemId: null,
        bioState: { sid: null, finalContent: null, polling: false, paused: false, canceled: false, completed: false, debugMode: false, stepSummary: '', lastBubbleStep: '' },
        memorials: [],
        form: {},
        uploadQueue: []
    };

    const FIELD_IDS = ['deceased_name', 'birth_date', 'death_date', 'occupation'];
    const STEP2_IDS = ['family_memory_text', 'last_wishes'];

    const STEP_BUBBLES = {
        BIO01: '我先把您提供的姓名、出生去世时间、职业这些基础信息梳理出来，建立这份传记的骨架。',
        BIO02: '我在检查重复、矛盾和缺失的信息，尽量把内容整理得更准确、顺畅。',
        BIO03: '我把人物经历按时间顺序重新排好，让整篇传记更像一条清晰的人生线。',
        BIO04: '我开始把这些材料写成完整的传记正文，尽量写得自然、温暖、像讲给家人听。',
        BIO05: '我会再读一遍全文，调整语气、节奏和细节，让成稿更完整、更耐读。',
        BIO06: '我会为传记进行排版并生成最终版本。',
    };

    const SAMPLE_DATA = {
        deceased_name: '陈文斌',
        birth_date: '1950',
        death_date: '2023',
        occupation: '中学语文教师',
        deceased_gender: '男',
        family_memory_text: `
父亲1972年从师范学院毕业后，被分配到家乡的县城一中任教。那时他才22岁，满怀理想。第一届学生中有不少比他小不了几岁，他却用扎实的学识和真诚的态度赢得了大家的尊重。他自费订阅《人民文学》《诗刊》，把最新的好文章带到课堂上。1975年，他带的第一个毕业班，语文平均分名列全县第一。


1981年，父亲被评为县级优秀教师。他开始尝试"情境教学法"，把课堂搬到操场、田野，让学生在大自然中感受文学之美。1985年第一个教师节，他收到了学生集体赠送的笔记本，扉页上写着："您让我们爱上了语文。"这一年，他加入了中国共产党。

1988年，父亲担任语文教研组长，组织编写了校本教材《古诗词选读》，被周边多所学校采用。


1993年，父亲被评为高级教师。他的学生小王考入北京大学中文系，后来成为知名作家，多次在作品中提及父亲的启蒙之恩。

1996年，父亲接手了一个"后进班"，班里学生普遍对学习失去信心。他没有放弃任何一个孩子，利用每天早读前和放学后的时间义务补课，周末还组织读书会。一年后，这个班的语文成绩从年级倒数第一跃升至第三名。家长会上，多位家长感动落泪。

1999年，父亲获得"省级骨干教师"称号。

2005年，父亲正式退休。告别讲台那天，他把自己收藏的300多册图书捐给了学校图书馆。他说："书是给人读的，放在我这里不如让孩子们看。"

退休后，父亲的生活依然忙碌而有规律：
- 每天清晨5点半起床，先练一小时书法，再读一小时书
- 每周二、四上午，在社区活动中心义务教老年人识字、写字
- 每月一次，回学校给年轻教师做教学指导
- 每年春节，免费为邻居写春联，一写就是十几年

2008年汶川地震，父亲捐出了三个月的退休金。他说："国家有难，匹夫有责。"

2010年，孙子出生。父亲开始写《育儿日记》，记录孙子的成长点滴，里面夹满了照片和手写的批注。他教孙子背《三字经》《弟子规》，用毛笔写识字卡片挂在墙上。

2015年，父亲被查出轻度阿尔茨海默症。记忆力开始衰退，但他从来没有忘记过学生的名字。偶尔糊涂时，他会拿起粉笔在墙上写板书，嘴里念叨着课文。母亲说，那是他一辈子的热爱，刻在骨子里了。

2020年疫情期间，父亲身体状况每况愈下，但仍然坚持每天看新闻、写日记。他用颤抖的手写下一行字："希望孩子们平安，希望国家好。"

2022年冬天，父亲最后一次"上课"——他把家人叫到一起，用虚弱的声音讲了半小时，内容是《岳阳楼记》里的"先天下之忧而忧，后天下之乐而乐"。讲完后，他靠在沙发上睡着了，脸上带着微笑。

2023年春天，父亲安详离世，享年73岁。

出殡那天，来了两百多位他曾经教过的学生。有人从千里之外赶回，有人带着已经成年的孩子。大家自发排成长队，眼含热泪送他最后一程。一位年过五旬的学生说："陈老师改变了我的一生，没有他，就没有今天的我。"

父亲一生清贫，却富足无比。他用一支粉笔，写下了桃李满天下的传奇。`
    };


    function renderSteps() {
        const steps = [
            ['1', '基本信息'],
            ['2', '回忆 & 风格'],
            ['3', '生成传记']
        ];
        const row = $('stepsRow');
        row.innerHTML = '';
        steps.forEach((s, i) => {
            if (i > 0) {
                const d = document.createElement('div');
                d.className = 'step-divider';
                row.appendChild(d);
            }
            const pill = document.createElement('div');
            pill.className = 'step-pill ' + (state.step === i + 1 ? 'active' : (state.step > i + 1 ? 'done' : ''));
            pill.innerHTML = `<span class="step-num">${s[0]}</span><span>${s[1]}</span>`;
            row.appendChild(pill);
        });
    }
    function clearAllStateAndStorage() {
        // 1. 重置 state 对象
        state.step = 1;
        state.currentMemId = null;
        state.bioState = {
            sid: null, finalContent: null, polling: false, paused: false, 
            canceled: false, completed: false, debugMode: false, 
            stepSummary: '', lastBubbleStep: '', editorOpen: false, editorContent: null
        };
        state.memorials = [];
        state.form = {};
        state.uploadQueue = [];

        // 2. 清除所有 localStorage 中与此功能相关的条目
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('NN_BIO_STEP_') || key === 'NN_BIO_STEP_LAST' || key.startsWith('NN_BIO_FORM_'))) {
                keysToRemove.push(key);
            }
        }
        keysToRemove.forEach(key => localStorage.removeItem(key));

        // 3. 重置表单元素
        FIELD_IDS.forEach(key => {
            const el = $('f_' + key);
            if (el) el.value = '';
        });
        STEP2_IDS.forEach(key => {
            const el = $('f_' + key);
            if (el) el.value = '';
        });
        // 重置性别为默认（男）
        const maleRadio = document.querySelector('input[name="gender"][value="男"]');
        if (maleRadio) maleRadio.checked = true;
        
        // 4. 重置传记相关UI
        const bioContent = $('bioContent');
        if (bioContent) bioContent.innerHTML = '';
        const bioEditor = $('bioEditor');
        if (bioEditor) bioEditor.value = '';
        const bioTitle = $('bioTitle');
        if (bioTitle) bioTitle.value = '';
        const bioProgress = $('bioProgress');
        if (bioProgress) {
            bioProgress.style.display = 'none';
            bioProgress.classList.remove('active');
        }
        const bioResult = $('bioResult');
        if (bioResult) bioResult.classList.add('hidden');
        const bioProgressBar = $('bioProgressBar');
        if (bioProgressBar) bioProgressBar.style.width = '0%';
        const bioProgressLabel = $('bioProgressLabel');
        if (bioProgressLabel) bioProgressLabel.textContent = '';
        
        // 5. 隐藏步骤气泡
        const stepBubble = $('bioStepBubble');
        if (stepBubble) stepBubble.classList.add('hidden');
        
        // 6. 隐藏编辑器包装器
        const editorWrap = $('bioEditorWrap');
        if (editorWrap) editorWrap.style.display = 'none';
        
        // 7. 确保显示第一步
        showStep(1, { silent: true, restoreForm: false });
    }

    function getStepStorageKey(memId = state.currentMemId) {
        return 'NN_BIO_STEP_' + (memId || 'default');
    }

    function getFormStorageKey(memId = state.currentMemId) {
        return 'NN_BIO_FORM_' + (memId || 'default');
    }

    function saveCurrentStep(n) {
        try {
            window.localStorage.setItem('NN_BIO_STEP_LAST', String(n));
            window.localStorage.setItem(getStepStorageKey(), String(n));
        } catch (e) {
            console.warn('save step failed:', e);
        }
    }

    function isFromHomePage() {
        // 方法1: 检查 document.referrer（上一个页面）
        const referrer = document.referrer;
        if (referrer) {
            // 检查是否从 index.html 或主页进入
            if (referrer.includes('/index.html') || 
                referrer.endsWith('/') || 
                referrer.includes('/home')) {
                console.log('检测到从主页进入，referrer:', referrer);
                return true;
            }
        }
        
        // 方法2: 检查 URL 参数（如果主页链接带了参数）
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('from') === 'home' || urlParams.get('reset') === 'true') {
            console.log('检测到 URL 参数标记');
            return true;
        }
        
        // 方法3: 检查 sessionStorage 标记（在主页点击时设置）
        if (sessionStorage.getItem('from_home_to_biography') === 'true') {
            sessionStorage.removeItem('from_home_to_biography'); // 清除标记，避免重复触发
            console.log('检测到 sessionStorage 标记');
            return true;
        }
        
        // 方法4: 检查是否是新会话（没有存储任何传记相关数据）
        const hasBioStorage = (() => {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.startsWith('NN_BIO_STEP_') || key === 'NN_BIO_STEP_LAST' || key.startsWith('NN_BIO_FORM_'))) {
                    return true;
                }
            }
            return false;
        })();
        
        // 如果没有任何存储数据，且不是通过刷新进入，则认为是首次进入
        if (!hasBioStorage && performance.navigation.type !== 1) {
            console.log('无存储数据且非刷新，视为首次进入');
            return true;
        }
        
        return false;
    }

    function resetStep3State() {
        console.log('离开 step3，重置传记生成状态');
        
        // 1. 如果有进行中的会话，取消它
        if (state.bioState.sid) {
            sendBioControl('cancel').catch(e => console.warn('取消会话失败:', e));
        }
        
        // 2. 重置 bioState
        state.bioState = {
            sid: null, 
            finalContent: null, 
            polling: false, 
            paused: false, 
            canceled: false, 
            completed: false, 
            debugMode: false, 
            stepSummary: '', 
            lastBubbleStep: '', 
            editorOpen: false, 
            editorContent: null
        };
        
        // 3. 重置 UI 元素
        const bioProgress = safeEl('bioProgress');
        if (bioProgress) {
            bioProgress.classList.remove('active');
            bioProgress.classList.add('hidden');
        }
        
        const bioResult = safeEl('bioResult');
        if (bioResult) bioResult.classList.add('hidden');
        
        const bioProgressBar = safeEl('bioProgressBar');
        if (bioProgressBar) bioProgressBar.style.width = '0%';
        
        const bioProgressLabel = safeEl('bioProgressLabel');
        if (bioProgressLabel) bioProgressLabel.textContent = '';
        
        const bioContent = safeEl('bioContent');
        if (bioContent) bioContent.innerHTML = '';
        
        const bioEditor = safeEl('bioEditor');
        if (bioEditor) bioEditor.value = '';
        
        const bioTitle = safeEl('bioTitle');
        if (bioTitle) bioTitle.value = '';
        
        // 4. 隐藏步骤气泡
        hideStepBubble();
        
        // 5. 更新按钮状态
        updateProgressActions();
    }

    function restoreCurrentStep() {
        try {
            const keys = [getStepStorageKey(), 'NN_BIO_STEP_LAST', 'NN_BIO_STEP_default'];
            for (const key of keys) {
                const raw = window.localStorage.getItem(key);
                const n = parseInt(raw || '0', 10);
                if ([1, 2, 3].includes(n)) return n;
            }
            return null;
        } catch (e) {
            return null;
        }
    }

    function saveFormState() {
        try {
            window.localStorage.setItem(getFormStorageKey(), JSON.stringify(state.form || {}));
        } catch (e) {
            console.warn('save form failed:', e);
        }
    }

    function restoreFormState() {
        try {
            const raw = window.localStorage.getItem(getFormStorageKey());
            if (!raw) return null;
            const data = JSON.parse(raw);
            return data && typeof data === 'object' ? data : null;
        } catch (e) {
            return null;
        }
    }

    function showStep(n, opts = {}) {
        if (state.step === 3 && n !== 3) {
            resetStep3State();
        }
        state.step = n;
        ['step1', 'step2', 'step3'].forEach((id, idx) => {
            $(id).classList.toggle('hidden', idx + 1 !== n);
        });
        renderSteps();
        if (opts.restoreForm) {
            writeForm(state.form);
        }
        if (!opts.silent) window.scrollTo({ top: 0, behavior: 'smooth' });
        saveCurrentStep(n);
        if (opts.restoreForm) saveFormState();
    }

    // async function init() {
    //     if (!NianAuth.requireAuth()) return;
    //     renderSteps();
    //     await loadMemorials();
    //     bindEvents();
    //     const restoredForm = restoreFormState();
    //     if (restoredForm) {
    //         state.form = { ...state.form, ...restoredForm };
    //     }
    //     applyDeepSearchFillIfPresent();
    //     const restored = restoreCurrentStep();
    //     if (restored) {
    //         showStep(restored, { silent: true });
    //     }
    // }

    async function loadMemorials() {
        try {
            const r = await NianAuth.fetch('/api/memorials');
            const d = await r.json();
            state.memorials = d.memorials || [];
            state.currentMemId = state.currentMemId || NianAuth.getActiveMemorialId() || (state.memorials[0] && state.memorials[0].memorial_id) || null;
            if (state.currentMemId) NianAuth.setActiveMemorialId(state.currentMemId);
            populateMemSelect();
            renderMemList();
        } catch (e) {
            console.warn('load memorials error:', e);
        }
    }

    function populateMemSelect() {
        const sel = $('memSelect');
        if (!sel) return;
        sel.innerHTML = '<option value="">-- 选择纪念对象 --</option>';
        state.memorials.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.memorial_id;
            opt.textContent = m.name || m.subject?.name || '未命名';
            sel.appendChild(opt);
        });
        if (state.currentMemId) sel.value = state.currentMemId;
    }

    function renderMemList() {
        const list = $('memList');
        if (!list) return;
        if (!state.memorials.length) {
            list.innerHTML = '<li style="padding: 10px; color: var(--muted-l); font-size: 0.85rem;">暂无纪念对象</li>';
            return;
        }
        list.innerHTML = state.memorials.map(m => `
            <li class="${m.memorial_id === state.currentMemId ? 'active' : ''}" onclick="selectMem('${m.memorial_id}')">
              <div class="n">${escapeHtml(m.name || m.subject?.name || '未命名')}</div>
              <div class="r">${escapeHtml(m.relation || m.subject?.relation || '—')}</div>
            </li>
        `).join('');
        const sel = $('memSelect');
        if (sel) sel.value = state.currentMemId || '';
    }

    function escapeHtml(text) {
        return String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[c]);
    }

    function bindEvents() {
        const btnFillTest = $('btnFillTest');
        const btnLoadDebug = $('btnLoadDebug');
        const btnToStep2 = $('btnToStep2');
        const btnToStep3 = $('btnToStep3');
        const btnBackTo1 = $('btnBackTo1');
        const btnBackTo2 = $('btnBackTo2');
        const btnPauseBio = $('btnPauseBio');
        const btnCancelBio = $('btnCancelBio');
        const btnRefreshBio = $('btnRefreshBio');
        const btnExportMenu = $('btnExportMenu');
        const exportMenu = $('exportMenu');
        const btnExportPDF = $('btnExportPDF');
        const btnExportDOCX = $('btnExportDOCX');

        const hideExportMenu = () => exportMenu?.classList.add('hidden');

        if (btnExportMenu) btnExportMenu.addEventListener('click', (e) => {
            e.stopPropagation();
            exportMenu?.classList.toggle('hidden');
        });
        if (btnExportPDF) btnExportPDF.addEventListener('click', async (e) => {
            e.stopPropagation();
            hideExportMenu();
            await exportToPDF();
        });
        if (btnExportDOCX) btnExportDOCX.addEventListener('click', async (e) => {
            e.stopPropagation();
            hideExportMenu();
            await exportToDOCX();
        });
        document.addEventListener('click', hideExportMenu);

        if (btnFillTest) btnFillTest.addEventListener('click', fillTestData);
        if (btnLoadDebug) btnLoadDebug.addEventListener('click', loadDebugMode);
        if (btnToStep2) btnToStep2.addEventListener('click', gotoStep2);
        if (btnToStep3) btnToStep3.addEventListener('click', gotoStep3);
        if (btnBackTo1) btnBackTo1.addEventListener('click', () => {
            stopBioPollingForNavigation();
            showStep(1, { restoreForm: true });
        });
        if (btnBackTo2) {
            btnBackTo2.addEventListener('click', () => {
                stopBioPollingForNavigation();
                resetStep3State(); // 离开 step3 时重置
                showStep(2, { restoreForm: true });
            });
        };
        if (btnPauseBio) btnPauseBio.addEventListener('click', async () => {
            if (!state.bioState.sid) return;
            if (state.bioState.paused) {
                try {
                    await sendBioControl('resume');
                    state.bioState.paused = false;
                    state.bioState.polling = true;
                    setText('bioProgressLabel', '恢复中...');
                    pollBioStatus();
                    updateProgressActions();
                } catch (e) {
                    alert('继续失败：' + e.message);
                }
                return;
            }
            if (!state.bioState.polling) return;
            try {
                await sendBioControl('pause');
                state.bioState.paused = true;
                state.bioState.polling = false;
                setText('bioProgressLabel', '已暂停');
                updateProgressActions();
            } catch (e) {
                alert('暂停失败：' + e.message);
            }
        });
        if (btnCancelBio) btnCancelBio.addEventListener('click', async () => {
            if (!state.bioState.sid) return;
            try {
                await sendBioControl('cancel');
                state.bioState.polling = false;
                state.bioState.paused = false;
                state.bioState.canceled = true;
                safeEl('bioProgress')?.classList.remove('active');
                setText('bioProgressLabel', '已取消');
                updateProgressActions();
            } catch (e) {
                alert('取消失败：' + e.message);
            }
        });
        if (btnRefreshBio) btnRefreshBio.addEventListener('click', async () => {
            if (state.bioState.sid && !state.bioState.completed) {
                // 重新生成：先取消当前会话，再从头新开一个会话并重新开始
                try {
                    await sendBioControl('cancel');
                } catch (e) {
                    console.warn('刷新时取消旧会话失败：', e.message);
                }
                state.bioState.polling = false;
                state.bioState.paused = false;
                state.bioState.canceled = false;
                state.bioState.completed = false;
                setText('bioProgressLabel', '重新生成中...');
                safeEl('bioProgressBar') && (safeEl('bioProgressBar').style.width = '0%');
                safeEl('bioProgress')?.classList.add('active');
                updateProgressActions();
                await startBiography();
                return;
            }
            if (!state.bioState.sid || state.bioState.completed) {
                await startBiography();
            }
        });
        const btnNew = $('btnNew');
        if (btnNew) {
            btnNew.addEventListener('click', () => {
                const nm = $('newMemModal'); if (nm) nm.classList.add('show');
            });
        }
        const cancelNewMem = $('cancelNewMem');
        if (cancelNewMem) {
            cancelNewMem.addEventListener('click', () => $('newMemModal').style.display = 'none');
        }
        const confirmNewMem = $('confirmNewMem');
        if (confirmNewMem) {
            confirmNewMem.addEventListener('click', createNewMemorial);
        }
        const memSelect = $('memSelect');
        if (memSelect) {
            memSelect.addEventListener('change', (e) => {
                if (e.target.value) selectMem(e.target.value);
            });
        }
        const uploadInput = $('upload_input');
        const uploadZone = $('uploadZone');
        if (uploadInput) {
            uploadInput.addEventListener('change', (e) => {
                console.log('upload_input change', e.target.files);
                prepareUpload(Array.from(e.target.files));
            });
            uploadInput.addEventListener('click', () => {
                uploadInput.value = '';
            });
        }
        if (uploadZone) {
            uploadZone.addEventListener('dragenter', preventDefault);
            uploadZone.addEventListener('dragover', preventDefault);
            uploadZone.addEventListener('drop', (e) => {
                preventDefault(e);
                if (e.dataTransfer?.files?.length) {
                    prepareUpload(Array.from(e.dataTransfer.files));
                }
            });
        }
        $('uploadCancel').addEventListener('click', hideUploadModal);
        $('uploadConfirm').addEventListener('click', confirmUpload);
    }

    function readStep1Form() {
        const f = {};
        FIELD_IDS.forEach(key => {
            const el = $('f_' + key);
            if (el) f[key] = el.value.trim();
        });
        const genderEl = document.querySelector('input[name="gender"]:checked');
        f.deceased_gender = genderEl ? genderEl.value : '男';
        return f;
    }

    function readStep2Form() {
        const f = {};
        STEP2_IDS.forEach(key => {
            const el = $('f_' + key);
            if (el) f[key] = el.value.trim();
        });
        return f;
    }

    function yearOnly(value) {
        const text = String(value || '').trim();
        const match = text.match(/(\d{4})/);
        return match ? match[1] : text;
    }

    function writeForm(data) {
        FIELD_IDS.forEach(key => {
            const el = $('f_' + key);
            if (!el || data[key] == null) return;
            if (key === 'birth_date' || key === 'death_date') {
                el.value = yearOnly(data[key]);
            } else {
                el.value = data[key];
            }
        });
        STEP2_IDS.forEach(key => {
            const el = $('f_' + key);
            if (el && data[key] != null) el.value = data[key];
        });
        if (data.deceased_gender) {
            const radio = document.querySelector(`input[name="gender"][value="${data.deceased_gender}"]`);
            if (radio) radio.checked = true;
        }
    }

    function fillTestData() {
        state.form = { ...state.form, ...SAMPLE_DATA };
        writeForm(state.form);
        saveFormState();
        gotoStep2();
    }

    function loadDebugMode() {
        state.form = { ...state.form, ...SAMPLE_DATA };
        writeForm(state.form);
        state.currentMemId = state.currentMemId || 'm_debug';
        NianAuth.setActiveMemorialId(state.currentMemId);
        const memSelect = $('memSelect');
        if (memSelect) {
            memSelect.value = state.currentMemId;
        }
        showStep(3);
        state.bioState.sid = null;
        state.bioState.finalContent = DEBUG_BIO_MARKDOWN;
        state.bioState.polling = false;
        state.bioState.paused = false;
        state.bioState.canceled = false;
        state.bioState.completed = true;
        state.bioState.debugMode = true;
        safeEl('bioProgress')?.classList.remove('active');
        safeEl('bioProgress')?.classList.add('hidden');
        safeEl('bioResult')?.classList.remove('hidden');
        applyServerBioCss('');
        const bioContent = safeEl('bioContent');
        if (bioContent) bioContent.innerHTML = mdToHtml(DEBUG_BIO_MARKDOWN);
        const bioEditor = safeEl('bioEditor');
        if (bioEditor) bioEditor.value = DEBUG_BIO_MARKDOWN;
        const bioTitleEl = $('bioTitle');
        if (bioTitleEl) bioTitleEl.value = '陈文斌 的个人传记（调试模式）';
        updateProgressActions();
        bindExportActions();
        alert('已进入调试模式，可直接测试导出、图片渲染与保存逻辑。');
    }

    function setPauseButtonMode() {
        const btnPause = $('btnPauseBio');
        if (!btnPause) return;
        if (state.bioState.paused) {
            btnPause.textContent = '▶';
            btnPause.title = '继续';
        } else {
            btnPause.textContent = '⏸';
            btnPause.title = '暂停';
        }
    }

    function updateProgressActions() {
        const btnPause = $('btnPauseBio');
        const btnCancel = $('btnCancelBio');
        const btnRefresh = $('btnRefreshBio');
        const active = !state.bioState.completed && !state.bioState.canceled;
        if (btnPause) btnPause.style.display = active ? 'inline-flex' : 'none';
        if (btnCancel) btnCancel.style.display = active ? 'inline-flex' : 'none';
        if (btnRefresh) btnRefresh.style.display = 'inline-flex';
        setPauseButtonMode();
    }

    async function sendBioControl(action) {
        if (!state.bioState.sid) return null;
        const res = await NianAuth.fetch('/api/biography/' + action + '/' + state.bioState.sid, {
            method: 'POST',
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || '控制请求失败');
        }
        return await res.json();
    }

    function normalizeBioKey(v) {
        return String(v || '').trim().replace(/\s+/g, '').toLowerCase();
    }

    function findMemorialByIdentity(name, birth, death) {
        const targetName = normalizeBioKey(name);
        const targetBirth = yearOnly(birth);
        const targetDeath = yearOnly(death);
        return state.memorials.find(m => {
            const metaName = normalizeBioKey(m.name || m.subject?.name || '');
            const metaBirth = yearOnly(m.birth_date || m.subject?.birth || '');
            const metaDeath = yearOnly(m.death_date || m.subject?.passing || '');
            return metaName === targetName && metaBirth === targetBirth && metaDeath === targetDeath;
        }) || null;
    }

    async function gotoStep2() {
        const step1 = readStep1Form();
        if (!step1.deceased_name) {
            alert('请先填写逝者姓名');
            return;
        }
        state.form = { ...state.form, ...step1 };
        saveFormState();
        await ensureCurrentMemorial(step1);
        showStep(2);
    }

    async function gotoStep3() {
        const step2 = readStep2Form();
        if (!step2.family_memory_text || step2.family_memory_text.length < 20) {
            alert('请填写家庭回忆与生平故事（至少 20 字）');
            return;
        }
        state.form = { ...state.form, ...step2 };
        saveFormState();
        if (!state.currentMemId) {
            alert('请先选择或创建一位纪念对象');
            showStep(1);
            return;
        }
        resetStep3State();
        showStep(3);
        await startBiography();
    }

    async function ensureCurrentMemorial(step1) {
        const name = step1?.deceased_name || '';
        if (!name) return null;
        const birth = yearOnly(step1?.birth_date || '');
        const death = yearOnly(step1?.death_date || '');
        const relation = state.form.relation || '';
        const note = state.form.family_memory_text || '';
        const matched = findMemorialByIdentity(name, birth, death);
        if (matched?.memorial_id) {
            state.currentMemId = matched.memorial_id;
            NianAuth.setActiveMemorialId(state.currentMemId);
            return state.currentMemId;
        }
        try {
            const r = await NianAuth.fetch('/api/memorials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, relation, note, birth_date: birth, death_date: death })
            });
            const d = await r.json();
            if (r.ok && d.memorial) {
                state.currentMemId = d.memorial.memorial_id;
                NianAuth.setActiveMemorialId(state.currentMemId);
                await loadMemorials();
                return state.currentMemId;
            }
            throw new Error(d.detail || d.error || '创建 memorial 失败');
        } catch (e) {
            console.warn('create memorial failed', e);
            throw e;
        }
    }

    async function getBioStatus() {
        const res = await NianAuth.fetch('/api/biography/status/' + state.bioState.sid);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || '无法获取进度状态');
        }
        return await res.json();
    }

    function stopBioPollingForNavigation() {
        state.bioState.polling = false;
        const progress = $('bioProgress');
        if (progress) progress.classList.remove('active');
    }

    window.addEventListener('beforeunload', () => {
        // 如果当前在 step3 且有活动会话，可以选择取消（可选）
        if (state.step === 3 && state.bioState.sid) {
            // 使用 sendBeacon 确保请求发送
            const url = '/api/biography/cancel/' + state.bioState.sid;
            navigator.sendBeacon(url, JSON.stringify({}));
        }
    });

    async function startBiography() {
        if (state.bioState.sid || state.bioState.polling) {
            console.log('清理旧状态后重新开始');
            resetStep3State();
        }
        state.bioState.finalContent = null;
        state.bioState.completed = false;
        state.bioState.paused = false;
        state.bioState.canceled = false;
        safeEl('bioResult')?.classList.add('hidden');
        if (safeEl('bioProgress')) {
            safeEl('bioProgress').style.display = 'block';
            safeEl('bioProgress').classList.remove('hidden');
        }
        setText('bioProgressLabel', '正在初始化...');
        if (safeEl('bioProgressBar')) safeEl('bioProgressBar').style.width = '0%';
        updateProgressActions();

        try {
            const mem = state.memorials.find(m => m.memorial_id === state.currentMemId) || {};
            const payload = {
                sid: null,
                form_data: {
                    user_id: NianAuth.getUser()?.user_id || null,
                    memorial_id: state.currentMemId,
                    deceased_name: state.form.deceased_name || mem.name || mem.subject?.name || '',
                    birth_date: state.form.birth_date || mem.subject?.birth || '',
                    death_date: state.form.death_date || mem.subject?.passing || '',
                    occupation: state.form.occupation || mem.subject?.occupation || '',
                    relation: mem.relation || mem.subject?.relation || '',
                    family_memory_text: state.form.family_memory_text || '',
                    last_wishes: state.form.last_wishes || '',
                    photos: []
                }
            };

            const r = await NianAuth.fetch('/api/biography/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.error || '启动失败');
            state.bioState.sid = d.session_id;
            state.bioState.polling = true;
            
            pollBioStatus();
            showStepBubble('BIO01','素材提取','开始');
            NianAuth.fetch('/api/biography/chain', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sid: state.bioState.sid })
            })
            .then(async (resp) => {
                if (resp.ok) return resp.json().catch(() => ({}));
                const err = await resp.json().catch(() => ({}));
                if (state.bioState.paused || state.bioState.canceled) return null;
                throw new Error(err.detail || err.message || '生成失败');
            })
            .catch(err => {
                if (state.bioState.paused || state.bioState.canceled) return;
                console.error('Chain failed:', err);
                state.bioState.polling = false;
                alert('生成失败：' + err.message);
            });
        } catch (e) {
            $('bioProgress').classList.remove('active');
            alert('生成失败：' + e.message);
            showStep(2);
        }
    }

    // async function pollStepsAndShowResult(currentStatus = null) {
    //     const steps = ['BIO01', 'BIO02', 'BIO03', 'BIO04', 'BIO05'];
    //     const labels = {
    //         'BIO01': '素材信息提取',
    //         'BIO02': '信息审核与去重',
    //         'BIO03': '时间线重建',
    //         'BIO04': '生成传记草稿',
    //         'BIO05': '质量评审与润色'
    //     };

    //     let status = currentStatus;
    //     if (!status) {
    //         status = await getBioStatus();
    //     }
    //     const skipSteps = Object.entries(status.step_status || {})
    //         .filter(([, value]) => value === 'approved')
    //         .map(([key]) => key);

    //     for (let i = 0; i < steps.length; i++) {
    //         const step = steps[i];
    //         if (skipSteps.includes(step)) continue;
    //         if (!state.bioState.polling) return;
    //         // 设置为当前步骤开始的进度
    //         const startPct = Math.round((i / steps.length) * 100);
    //         $('bioProgressLabel').textContent = `${labels[step]}（正在执行...）`;
    //         $('bioProgressBar').style.width = startPct + '%';

    //         const stepRes = await NianAuth.fetch('/api/biography/step/' + step, {
    //             method: 'POST',
    //             headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify({ sid: state.bioState.sid })
    //         });
    //         if (!stepRes.ok) {
    //             throw new Error('步骤 ' + step + ' 执行失败');
    //         }

    //         // 完成当前步骤后的进度
    //         const donePct = Math.round(((i + 1) / steps.length) * 100);
    //         $('bioProgressLabel').textContent = `${labels[step]}（已完成）`;
    //         $('bioProgressBar').style.width = donePct + '%';

    //         await new Promise(res => setTimeout(res, 400));
    //         if (!state.bioState.polling || state.bioState.paused) return;
    //     }

    //     state.bioState.polling = false;
    //     state.bioState.completed = true;
    //     updateProgressActions();
    //     await showBioResult();
    // }

    function pollBioStatus() {
        if (!state.bioState.polling || state.bioState.paused) return;
        NianAuth.fetch('/api/biography/status/' + state.bioState.sid)
            .then(r => r.json())
            .then(d => {
                if (!state.bioState.polling || state.bioState.paused) return;
                const progress = (d.steps_completed / d.total_steps) * 100;
                const stepNames = {
                    'BIO01': '素材提取', 'BIO02': '审核去重', 
                    'BIO03': '时间线重建', 'BIO04': '传记生成', 'BIO05': '质量评审', 'BIO06': '排版渲染'
                };
                // const currentStep = d.current_step || 'BIO01';
                const currentStepName = stepNames[d.current_step] || d.current_step || '处理中';
            
                setText('bioProgressLabel', `${currentStepName} (${Math.round(progress)}%)`);
                const bioProgressBar = safeEl('bioProgressBar');
                if (bioProgressBar) bioProgressBar.style.width = progress + '%';

                if (d.current_step && d.current_step !== state.bioState.lastBubbleStep && d.status !== 'completed') {
                    const bubbleStatus = '进行中';
                    showStepBubble(d.current_step, currentStepName, bubbleStatus);
                }

                if (d.status === 'completed') {
                    state.bioState.polling = false;
                    state.bioState.completed = true;
                    updateProgressActions();
                    hideStepBubble();
                    showBioResult();
                } else if (d.status === 'paused') {
                    state.bioState.polling = false;
                    state.bioState.paused = true;
                    setText('bioProgressLabel', '已暂停');
                    updateProgressActions();
                } else if (d.status === 'canceled') {
                    state.bioState.polling = false;
                    state.bioState.canceled = true;
                    setText('bioProgressLabel', '已取消');
                    safeEl('bioProgress')?.classList.remove('active');
                    updateProgressActions();
                } else if (d.status === 'failed') {
                    state.bioState.polling = false;
                    safeEl('bioProgress')?.classList.remove('active');
                    alert('生成失败：' + (d.error || '未知错误'));
                } else {
                    setTimeout(pollBioStatus, 2000);
                }
            })
            .catch(() => {
                if (state.bioState.polling) setTimeout(pollBioStatus, 3000);
            });
    }
    function hideStepBubble() {
        const bubble = safeEl('bioStepBubble');
        if (bubble) {
            bubble.classList.add('hidden');
        }
    }
    function safeEl(id) {
        return $(id);
    }

    function setText(id, text) {
        const el = safeEl(id);
        if (el) el.textContent = text;
    }

    function setValue(id, value) {
        const el = safeEl(id);
        if (el) el.value = value;
    }

    function showStepBubble(stepId, currentStepName, statusLabel) {
        const bubble = safeEl('bioStepBubble');
        if (!bubble) return;
        const statusText = statusLabel || '完成';
        const text = STEP_BUBBLES[stepId] || `${currentStepName || '当前步骤'} ${statusText}。`;
        bubble.innerHTML = `\n            <div class="bubble-title">${escapeHtml(currentStepName || '步骤')}</div>\n            <div class="bubble-text">${escapeHtml(text)}</div>\n        `;
        bubble.classList.remove('hidden');
        state.bioState.lastBubbleStep = stepId || '';
    }

    function applyDeepSearchFillIfPresent() {
        try {
            const raw = window.localStorage.getItem('NN_DEEP_SEARCH_FILL');
            if (!raw) return;
            const payload = JSON.parse(raw);
            if (!payload || !payload.fields) return;
            const fields = payload.fields;
            state.form = { ...state.form, ...fields };
            writeForm(fields);
            if (payload.target === 'biography') {
                const familyMemory = fields.family_memory_text || fields['family_memory_text'];
                if (familyMemory) {
                    const step2El = $('f_family_memory_text');
                    if (step2El) step2El.value = familyMemory;
                }
            }
            if (payload.fields.deceased_name && !state.currentMemId) {
                state.currentMemId = NianAuth.getActiveMemorialId() || null;
            }
            const familyMemory = fields.family_memory_text || fields['family_memory_text'];
            if (familyMemory) {
                const fmEl = $('f_family_memory_text');
                if (fmEl) fmEl.value = familyMemory;
            }
            window.localStorage.removeItem('NN_DEEP_SEARCH_FILL');
        } catch (e) {
            console.warn('apply deep search fill failed:', e);
        }
    }

    function bindExportActions() {
        const pdfBtn = $('btnExportPDF');
        const docxBtn = $('btnExportDOCX');
        const htmlBtn = $('btnExportHTML');
        const toggleEditBtn = $('btnToggleEdit');
        if (pdfBtn && !pdfBtn.dataset.bound) {
            pdfBtn.dataset.bound = '1';
            pdfBtn.addEventListener('click', exportToPDF);
        }
        if (docxBtn && !docxBtn.dataset.bound) {
            docxBtn.dataset.bound = '1';
            docxBtn.addEventListener('click', exportToDOCX);
        }
        if (htmlBtn && !htmlBtn.dataset.bound) {
            htmlBtn.dataset.bound = '1';
            htmlBtn.addEventListener('click', exportToHTML);
        }
        if (toggleEditBtn && !toggleEditBtn.dataset.bound) {
            toggleEditBtn.dataset.bound = '1';
            toggleEditBtn.addEventListener('click', toggleEditor);
        }
    }

    async function showBioResult() {
        try {
            const r = await NianAuth.fetch('/api/biography/result/' + state.bioState.sid + '?embed_images=true');
            const d = await r.json();
            safeEl('bioProgress')?.classList.remove('active');
            safeEl('bioResult')?.classList.remove('hidden');
            const bioText = d.biography_final || '';
            state.bioState.finalContent = bioText;
            state.bioState.editorContent = bioText;
            applyServerBioCss(d.bio_css || '');
            renderBioContent(bioText);
            const selectedMem = state.memorials.find(m => m.memorial_id === state.currentMemId);
            const bioTitleEl = $('bioTitle');
            if (bioTitleEl) {
                bioTitleEl.value = (selectedMem?.name || selectedMem?.subject?.name || '传记') + ' 的个人传记';
            }
            state.bioState.completed = true;
            updateProgressActions();
            bindExportActions();
            syncEditorToContent();
        } catch (e) {
            alert('获取结果失败：' + e.message);
            safeEl('bioProgress')?.classList.remove('active');
        }
    }

    function renderInlineMarkdown(text) {
        if (!text) return '';
        let out = escapeHtml(text);
        out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        out = out.replace(/(^|[^*])\*(?!\s)(.+?)(?!\s)\*(?!\*)/g, '$1<em>$2</em>');
        out = out.replace(/`(.+?)`/g, '<code>$1</code>');
        out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer noopener">$1</a>');
        return out;
    }

    function mdToHtml(txt) {
        if (!txt) return '';
        const lines = txt.split('\n');
        let html = '';
        let para = [];
        const flushParagraph = () => {
            if (!para.length) return;
            html += '<p>' + para.map(renderInlineMarkdown).join('<br>') + '</p>';
            para = [];
        };
        const normalizeImageUrl = (url) => {
            if (!url) return url;
            return url.replace(/\&amp;/g, '&');
        };
        lines.forEach(line => {
            const headingMatch = line.match(/^\s*#{1,6}\s*(.*)$/);
            if (headingMatch && headingMatch[1].trim()) {
                flushParagraph();
                html += '<h2 class="bio-title bio-title-center">' + renderInlineMarkdown(headingMatch[1].trim()) + '</h2>';
                return;
            }
            if (/^\s*$/.test(line)) {
                flushParagraph();
                return;
            }
            const imageMatch = line.match(/^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$/);
            if (imageMatch) {
                flushParagraph();
                const rawAlt = imageMatch[1].trim();
                const imageUrl = normalizeImageUrl(imageMatch[2].trim());
                const imageClass = html.length > 0 ? 'bio-image wrap-left' : 'bio-image';
                html += '<div class="' + imageClass + '"><img src="' + escapeHtml(imageUrl) + '" alt="' + escapeHtml(rawAlt) + '">';
                if (rawAlt) html += '<div class="bio-image-caption">' + renderInlineMarkdown(rawAlt) + '</div>';
                html += '</div>';
                return;
            }
            para.push(line);
        });
        flushParagraph();
        return html;
    }

    function downloadBio() {
        const content = getCurrentBioMarkdown();
        if (!content) {
            alert('没有可下载的内容');
            return;
        }
        const selectedMem = state.memorials.find(m => m.memorial_id === state.currentMemId);
        const name = selectedMem?.name || selectedMem?.subject?.name || '传记';
        const text = name + ' 的个人传记\n\n' + content;
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name + '_传记.md';
        a.click();
        URL.revokeObjectURL(url);
    }
    function notify(message) {
        if (typeof showToast === 'function') {
            showToast(message);
        } else {
            console.log(message);
        }
    }

    function triggerDownload(filename, content, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    function getCurrentBioMarkdown() {
        const editor = $('bioEditor');
        if (state.bioState.editorOpen && editor) return editor.value;
        return state.bioState.finalContent || '';
    }

    function applyServerBioCss(cssText) {
        const id = 'bio-server-css';
        let style = document.getElementById(id);
        if (!cssText) {
            if (style) style.remove();
            return;
        }
        if (!style) {
            style = document.createElement('style');
            style.id = id;
            document.head.appendChild(style);
        }
        style.textContent = cssText;
    }

    function renderBioContent(markdownText) {
        const content = safeEl('bioContent');
        if (content) content.innerHTML = mdToHtml(markdownText || '');
    }

    function syncEditorToContent() {
        const editorWrap = safeEl('bioEditorWrap');
        const editor = safeEl('bioEditor');
        if (!editor || !editorWrap) return;
        editor.value = state.bioState.editorContent || state.bioState.finalContent || '';
        editorWrap.style.display = state.bioState.editorOpen ? 'block' : 'none';
    }

    function toggleEditor() {
        const editorWrap = safeEl('bioEditorWrap');
        const editor = safeEl('bioEditor');
        const content = safeEl('bioContent');
        if (!editorWrap || !editor || !content) return;
        state.bioState.editorOpen = !state.bioState.editorOpen;
        editorWrap.style.display = state.bioState.editorOpen ? 'block' : 'none';
        content.style.display = state.bioState.editorOpen ? 'none' : 'block';
        if (state.bioState.editorOpen) {
            editor.value = state.bioState.editorContent || state.bioState.finalContent || '';
            setText('btnToggleEdit', '预览');
        } else {
            state.bioState.editorContent = editor.value;
            state.bioState.finalContent = editor.value;
            renderBioContent(editor.value);
            setText('btnToggleEdit', '编辑');
        }
    }

    function ensureEditorSync() {
        const editor = safeEl('bioEditor');
        if (editor) {
            editor.addEventListener('input', () => {
                state.bioState.editorContent = editor.value;
                state.bioState.finalContent = editor.value;
            });
        }
    }

    function makeDebugExportHtml(title, content) {
        return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${escapeHtml(title)}</title></head><body><div style="max-width:860px;margin:0 auto;padding:32px;white-space:pre-wrap;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.85;font-size:16px;">${escapeHtml(content)}</div></body></html>`;
    }

    // 导出 PDF
    async function exportToPDF() {
        if (!state.bioState.sid) {
            alert('请先生成传记');
            return;
        }
        try {
            notify('正在生成PDF，请稍候...');
            const response = await NianAuth.fetch(`/api/biography/export-pdf/${state.bioState.sid}?embed_images=true`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || '导出失败');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${state.form.deceased_name || '传记'}_个人传记.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            notify('PDF 导出成功！');
        } catch (error) {
            console.error('PDF导出失败:', error);
            alert('PDF导出失败：' + error.message);
        }
    }

    // 导出 DOCX
    async function exportToDOCX() {
        if (!state.bioState.sid) {
            alert('请先生成传记');
            return;
        }
        try {
            notify('正在生成Word文档，请稍候...');
            const response = await NianAuth.fetch(`/api/biography/export-docx/${state.bioState.sid}?embed_images=true`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || '导出失败');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${state.form.deceased_name || '传记'}_个人传记.docx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            notify('Word 文档导出成功！');
        } catch (error) {
            console.error('DOCX导出失败:', error);
            alert('DOCX导出失败：' + error.message);
        }
    }

    async function exportToHTML() {
        const title = `${state.form.deceased_name || '传记'}_个人传记`;
        const html = makeDebugExportHtml(title, getCurrentBioMarkdown() || state.bioState.finalContent || '');
        triggerDownload(`${title}.html`, html, 'text/html;charset=utf-8');
        notify('已导出 HTML，可直接在浏览器打开或打印另存为 PDF');
    }

// 添加导出按钮到页面
    function addExportButtons() {
        const actions = $('bioResultActions');
        if (actions) {
            actions.innerHTML += `
                <button class="btn btn-secondary" id="btnExportPDF" type="button">导出 PDF</button>
                <button class="btn btn-secondary" id="btnExportDOCX" type="button">导出 Word</button>
            `;
        
            $('btnExportPDF')?.addEventListener('click', exportToPDF);
            $('btnExportDOCX')?.addEventListener('click', exportToDOCX);
        }
    }
    async function saveBio() {
        const titleEl = $('bioTitle');
        const title = titleEl ? titleEl.value.trim() : '';
        const content = getCurrentBioMarkdown();
        if (!title) {
            alert('请输入传记标题');
            return;
        }
        if (!content) {
            alert('没有内容可保存');
            return;
        }
        if (state.bioState.editorOpen) {
            state.bioState.editorContent = content;
            state.bioState.finalContent = content;
            renderBioContent(content);
        }
        try {
            const user = NianAuth.getUser() || {};
            const r = await NianAuth.fetch('/api/biography/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sid: state.bioState.sid,
                    title: title,
                    user_id: user.user_id,
                    memorial_id: state.currentMemId
                })
            });
            const d = await r.json();
            if (d.ok) {
                alert('✓ 已保存到资料库');
            } else {
                alert('保存失败：' + (d.error || d.detail || '未知错误'));
            }
        } catch (e) {
            alert('保存失败：' + e.message);
        }
    }

    async function createNewMemorial() {
        const nameEl = $('newMemName');
        const name = nameEl ? nameEl.value.trim() : '';
        if (!name) {
            alert('请输入姓名');
            return;
        }
        try {
            const r = await NianAuth.fetch('/api/memorials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, relation: '', note: '' })
            });
            const d = await r.json();
            if (r.ok && d.memorial) {
                state.currentMemId = d.memorial.memorial_id;
                NianAuth.setActiveMemorialId(state.currentMemId);
                $('newMemName').value = '';
                const nm = $('newMemModal'); if (nm) nm.classList.remove('show');
                await loadMemorials();
            } else {
                alert('创建失败：' + (d.error || '未知错误'));
            }
        } catch (e) {
            alert('创建失败：' + e.message);
        }
    }

    async function init() {
        if (!NianAuth.requireAuth()) return;
        
        renderSteps();
        await loadMemorials();
        bindEvents();
        
        // 检测是否从主页进入
        const fromHomePage = (() => {
            const referrer = document.referrer;
            return referrer && (
                referrer.includes('/index.html') || 
                referrer.endsWith('/') ||
                referrer.includes('/index')
            );
        })();
        
        if (fromHomePage) {
            // 从主页进入：清除所有状态，重新开始
            console.log('从主页进入，清除所有历史状态');
            clearAllStateAndStorage();
            showStep(1, { silent: true });
            // 聚焦到第一个输入框
            const firstNameField = $('f_deceased_name');
            if (firstNameField) firstNameField.focus();
        } else {
            // 正常恢复之前的状态（但不恢复 step3 的生成状态）
            console.log('正常恢复之前的状态');
            const restoredForm = restoreFormState();
            if (restoredForm) {
                state.form = { ...state.form, ...restoredForm };
            }
            applyDeepSearchFillIfPresent();
            
            const restoredStep = restoreCurrentStep();
            
            if (restoredStep === 3) {
                // 如果刷新后停留在 step3，只恢复表单和步骤显示，不恢复生成状态
                console.log('在 step3 刷新，只恢复界面，不恢复生成状态');
                showStep(3, { silent: true, restoreForm: true });
                // 确保 step3 状态是干净的，不自动开始生成
                resetStep3State();
                // 显示提示，让用户手动开始
                setText('bioProgressLabel', '点击"生成传记"按钮开始 6 步流程');
                const btnRefresh = $('btnRefreshBio');
                if (btnRefresh) {
                    btnRefresh.style.display = 'inline-flex';
                    btnRefresh.textContent = '生成传记';
                }
                const bioProgress = safeEl('bioProgress');
                if (bioProgress) {
                    bioProgress.classList.remove('active');
                    bioProgress.classList.add('hidden');
                }
            } else if (restoredStep) {
                showStep(restoredStep, { silent: true, restoreForm: true });
            } else {
                showStep(1, { silent: true });
            }
        }
    };

    async function prepareUpload(files) {
        console.log('biography upload prepare', files, state.currentMemId);
        if (!files || !files.length) return;
        if (!state.currentMemId) {
            const step1 = readStep1Form();
            if (!step1.deceased_name) {
                alert('请先填写逝者姓名并进入下一步，以创建纪念对象。');
                return;
            }
            await ensureCurrentMemorial(step1.deceased_name);
            if (!state.currentMemId) {
                alert('无法创建纪念对象，请稍后再试。');
                return;
            }
        }
        state.uploadQueue = files;
        renderUploadPreview();
        const descEl = $('uploadDesc');
        if (descEl) descEl.value = '';
        const um = $('uploadModal'); if (um) um.classList.add('show');
    }

    function hideUploadModal() {
        const um = $('uploadModal'); if (um) um.classList.remove('show');
        const uploadInput = $('upload_input');
        if (uploadInput) uploadInput.value = '';
    }

    function renderUploadPreview() {
        const preview = $('uploadPreview');
        if (!preview) return;
        preview.innerHTML = state.uploadQueue.map(file => {
            const icon = file.type.startsWith('image/') ? '[图]' : (file.type.startsWith('audio/') ? '[音]' : (file.type.startsWith('video/') ? '[视]' : '[文]'));
            const size = file.size > 1024 * 1024 ? (file.size / 1024 / 1024).toFixed(1) + ' MB' : (file.size / 1024).toFixed(1) + ' KB';
            return `<div class="upload-modal-row"><span class="ic">${icon}</span><div style="text-align:left"><div style="font-weight:600">${escapeHtml(file.name)}</div><div style="color:#8a7654;font-size:.85rem">${size}</div></div></div>`;
        }).join('');
    }

    async function confirmUpload() {
        const desc = $('uploadDesc')?.value.trim() || '';
        await uploadFiles(desc);
        hideUploadModal();
    }

    async function uploadFiles(description) {
        const list = $('uploadList');
        if (!list || !state.uploadQueue.length) return;

        for (const file of state.uploadQueue) {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('description', description);
            try {
                const r = await NianAuth.fetch(`/api/memorials/${state.currentMemId}/upload`, {
                    method: 'POST',
                    body: fd,
                });
                if (!r.ok) {
                    const text = await r.text();
                    throw new Error(text || '上传失败');
                }
                if (file.type.startsWith('image/')) {
                    const url = URL.createObjectURL(file);
                    list.insertAdjacentHTML('beforeend', `<img class="upload-thumb" src="${url}" alt="">`);
                } else {
                    list.insertAdjacentHTML('beforeend', `<div class="upload-thumb" style="display:flex;align-items:center;justify-content:center;background:var(--surf3);font-size:.7rem;color:var(--muted-l);">${escapeHtml(file.name.slice(0, 12))}</div>`);
                }
            } catch (e) {
                alert('文件上传失败：' + e.message);
                console.warn('upload failed', e);
            }
        }
        if (state.uploadQueue.length) {
            alert('上传完成，已保存描述信息。');
        }
        state.uploadQueue = [];
    }

    function preventDefault(e) {
        if (e && e.preventDefault) {
            e.preventDefault();
            e.stopPropagation();
        }
    }

    document.addEventListener('DOMContentLoaded', init);
})();

