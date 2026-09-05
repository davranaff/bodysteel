(function () {
  'use strict';

  const BLOCKED_ELEMENTS = 'script,iframe,object,embed,style,svg,math,template';
  const BLOCKED_STYLE = /(?:@import|behavior\s*:|-moz-binding|expression\s*\(|javascript\s*:|url\s*\()/i;
  const HTML_ENTITIES = {'&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;'};
  const URL_ATTRIBUTES = new Set(['href', 'poster', 'src']);
  const commands = [
    ['Отменить', '↶', 'undo'],
    ['Повторить', '↷', 'redo'],
    ['Жирный', 'B', 'bold'],
    ['Курсив', 'I', 'italic'],
    ['Подчёркнутый', 'U', 'underline'],
    ['Обычный текст', 'P', 'formatBlock', 'p'],
    ['Заголовок 2', 'H2', 'formatBlock', 'h2'],
    ['Заголовок 3', 'H3', 'formatBlock', 'h3'],
    ['Маркированный список', '• Список', 'insertUnorderedList'],
    ['Нумерованный список', '1. Список', 'insertOrderedList'],
    ['Цитата', '❝', 'formatBlock', 'blockquote'],
    ['Очистить форматирование', 'Tx', 'removeFormat'],
  ];

  function sanitizeHtml(html) {
    const documentCopy = new DOMParser().parseFromString(html || '', 'text/html');
    documentCopy.querySelectorAll(BLOCKED_ELEMENTS).forEach((node) => node.remove());
    documentCopy.querySelectorAll('*').forEach((element) => {
      Array.from(element.attributes).forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim();
        if (name.startsWith('on') || name === 'srcdoc' || name === 'srcset') {
          element.removeAttribute(attribute.name);
        } else if (name === 'style' && BLOCKED_STYLE.test(value)) {
          element.removeAttribute(attribute.name);
        } else if (URL_ATTRIBUTES.has(name) && /^(?:javascript|data|vbscript|blob):|^\/\//i.test(value)) {
          element.removeAttribute(attribute.name);
        }
      });
    });
    return documentCopy.body.innerHTML;
  }
  function escapeHtml(value) {
    return String(value || '').replace(/[&"<>]/g, (character) => HTML_ENTITIES[character]);
  }
  function plainTextToHtml(value) {
    return escapeHtml(value).replace(/\r\n?|\n/g, '<br>');
  }
  function createButton(label, text, className) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className || 'bs-rich-html__button';
    button.title = label;
    button.setAttribute('aria-label', label);
    button.textContent = text;
    button.addEventListener('mousedown', (event) => event.preventDefault());
    return button;
  }

  function enhance(textarea) {
    if (textarea.dataset.richHtmlReady === 'true') return;
    textarea.dataset.richHtmlReady = 'true';

    const editor = document.createElement('div');
    editor.className = 'bs-rich-html';
    const toolbar = document.createElement('div');
    toolbar.className = 'bs-rich-html__toolbar';
    toolbar.setAttribute('role', 'toolbar');
    toolbar.setAttribute('aria-label', 'Форматирование текста');
    const surface = document.createElement('div');
    surface.className = 'bs-rich-html__surface';
    surface.contentEditable = 'true';
    surface.setAttribute('role', 'textbox');
    surface.setAttribute('aria-multiline', 'true');
    surface.setAttribute('aria-label', 'Содержимое');
    surface.dataset.placeholder = 'Введите текст или вставьте готовый контент…';
    surface.innerHTML = sanitizeHtml(textarea.value);
    const status = document.createElement('span');
    status.className = 'bs-rich-html__status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    const footer = document.createElement('div');
    footer.className = 'bs-rich-html__footer';
    footer.append(status);
    let sourceMode = false;
    let savedRange = null;

    function sync() {
      if (!sourceMode) textarea.value = surface.innerHTML;
    }

    function rememberSelection() {
      const selection = window.getSelection();
      if (selection.rangeCount && surface.contains(selection.anchorNode)) {
        savedRange = selection.getRangeAt(0).cloneRange();
      }
    }

    function restoreSelection() {
      surface.focus();
      if (!savedRange) return;
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange);
    }

    function insertHtml(html) {
      restoreSelection();
      document.execCommand('insertHTML', false, html);
      rememberSelection();
      sync();
    }

    async function upload(file) {
      if (!file || !file.type.startsWith('image/')) throw new Error('Выберите изображение.');
      if (file.size > 10 * 1024 * 1024) throw new Error('Изображение должно быть не больше 10 МБ.');
      const csrf = textarea.form?.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
      const body = new FormData();
      body.append('image', file, file.name || 'clipboard-image');
      const response = await fetch(textarea.dataset.uploadUrl, {
        method: 'POST',
        body,
        headers: {'X-CSRFToken': csrf},
        credentials: 'same-origin',
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.url) throw new Error(payload.error || 'Не удалось загрузить изображение.');
      return payload.url;
    }

    async function insertFiles(files) {
      status.textContent = 'Загрузка изображения…';
      try {
        for (const file of files) {
          const url = await upload(file);
          insertHtml(`<img src="${escapeHtml(url)}" alt="">`);
        }
        status.textContent = files.length > 1 ? 'Изображения загружены' : 'Изображение загружено';
      } catch (error) {
        status.textContent = error.message;
      }
    }

    commands.forEach(([label, text, command, value]) => {
      const button = createButton(label, text);
      if (command === 'bold') button.classList.add('is-bold');
      if (command === 'italic') button.classList.add('is-italic');
      if (command === 'underline') button.classList.add('is-underline');
      button.addEventListener('click', () => {
        restoreSelection();
        document.execCommand(command, false, value || null);
        rememberSelection();
        sync();
      });
      toolbar.append(button);
    });

    const linkButton = createButton('Добавить ссылку', '🔗');
    linkButton.addEventListener('click', () => {
      const url = window.prompt('Адрес ссылки (https://… или /страница):');
      if (!url || /^(?:javascript|data|vbscript):|^\/\//i.test(url.trim())) return;
      restoreSelection();
      document.execCommand('createLink', false, url.trim());
      sync();
    });
    toolbar.append(linkButton);

    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/jpeg,image/png,image/webp,image/gif';
    fileInput.multiple = true;
    fileInput.hidden = true;
    const imageButton = createButton('Вставить изображение', '🖼 Изображение');
    imageButton.addEventListener('click', () => {
      rememberSelection();
      fileInput.click();
    });
    fileInput.addEventListener('change', async () => {
      await insertFiles(Array.from(fileInput.files || []));
      fileInput.value = '';
    });
    toolbar.append(imageButton, fileInput);

    const sourceButton = createButton('Показать HTML-код', '</>', 'bs-rich-html__button bs-rich-html__source-toggle');
    sourceButton.addEventListener('click', () => {
      sourceMode = !sourceMode;
      toolbar.querySelectorAll('button:not(.bs-rich-html__source-toggle)').forEach((button) => {
        button.disabled = sourceMode;
      });
      if (sourceMode) {
        sync();
        textarea.hidden = false;
        surface.hidden = true;
        sourceButton.classList.add('is-active');
        sourceButton.title = 'Вернуться к визуальному редактору';
        sourceButton.setAttribute('aria-label', sourceButton.title);
        textarea.focus();
      } else {
        surface.innerHTML = sanitizeHtml(textarea.value);
        textarea.value = surface.innerHTML;
        textarea.hidden = true;
        surface.hidden = false;
        sourceButton.classList.remove('is-active');
        sourceButton.title = 'Показать HTML-код';
        sourceButton.setAttribute('aria-label', sourceButton.title);
        surface.focus();
      }
    });
    toolbar.append(sourceButton);

    surface.addEventListener('input', sync);
    surface.addEventListener('keyup', rememberSelection);
    surface.addEventListener('mouseup', rememberSelection);
    surface.addEventListener('focus', rememberSelection);
    surface.addEventListener('paste', async (event) => {
      const files = Array.from(event.clipboardData?.items || [])
        .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
        .map((item) => item.getAsFile()).filter(Boolean);
      rememberSelection();
      if (files.length) {
        event.preventDefault();
        await insertFiles(files);
        return;
      }
      const text = event.clipboardData?.getData('text/plain');
      if (text) {
        event.preventDefault();
        insertHtml(plainTextToHtml(text));
        status.textContent = 'Текст вставлен без исходного форматирования';
        return;
      }
      const html = event.clipboardData?.getData('text/html');
      if (html) {
        event.preventDefault();
        const documentCopy = new DOMParser().parseFromString(html, 'text/html');
        const fallbackText = documentCopy.body.textContent || '';
        insertHtml(fallbackText.trim() ? plainTextToHtml(fallbackText) : sanitizeHtml(html));
      }
    });
    textarea.form?.addEventListener('submit', sync);
    textarea.hidden = true;
    textarea.parentNode.insertBefore(editor, textarea);
    editor.append(toolbar, surface, footer, textarea);
  }

  function initialize(root) {
    root.querySelectorAll?.('textarea[data-rich-html-editor="true"]').forEach(enhance);
  }

  document.addEventListener('DOMContentLoaded', () => initialize(document));
  document.addEventListener('formset:added', (event) => initialize(event.target));
}());
