/*
 * This file is part of Supysonic.
 * Supysonic is a Python implementation of the Subsonic server API.
 *
 * Copyright (C) 2017-2024 Óscar García Amor
 *               2017-2024 Alban 'spl0k' Féron
 *
 * Distributed under terms of the GNU AGPLv3 license.
 */

const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

document.querySelectorAll('.modal').forEach(function (modal) {
  modal.addEventListener('show.bs.modal', function (e) {
    var href = e.relatedTarget.getAttribute('data-href');
    var btnOk = modal.querySelector('.btn-ok');
    btnOk.setAttribute('href', href);
    btnOk.addEventListener('click', function () {
      var modalInstance = bootstrap.Modal.getInstance(modal);
      modalInstance.hide();
    }, { once: true });
  });
});

function setTheme(theme) {
  if (theme === 'auto') {
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.body.setAttribute('data-bs-theme', systemTheme);
  } else {
    document.body.setAttribute('data-bs-theme', theme);
  }
}

function applyLanguage(language) {
  const activeLanguage = language === 'zh' ? 'zh' : 'en';
  document.documentElement.lang = activeLanguage === 'zh' ? 'zh-Hans' : 'en';
  document.body.setAttribute('data-language', activeLanguage);

  document.querySelectorAll('[data-i18n-en][data-i18n-zh]').forEach(function (node) {
    const attr = node.getAttribute('data-i18n-attr');
    const text = activeLanguage === 'zh' ? node.getAttribute('data-i18n-zh') : node.getAttribute('data-i18n-en');
    if (!text) {
      return;
    }

    if (attr) {
      node.setAttribute(attr, text);
      if (attr === 'placeholder' && node.getAttribute('aria-label') === node.getAttribute('data-i18n-en')) {
        node.setAttribute('aria-label', text);
      }
      return;
    }

    node.textContent = text;
  });

  document.querySelectorAll('[data-language-toggle]').forEach(function (button) {
    const isActive = button.getAttribute('data-language-toggle') === activeLanguage;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
  });
}

function getLanguage() {
  return document.body.getAttribute('data-language') === 'zh' ? 'zh' : 'en';
}

function getI18nText(node, fallback) {
  if (!node) {
    return fallback || '';
  }

  const language = getLanguage();
  return language === 'zh'
    ? node.getAttribute('data-i18n-zh') || fallback || ''
    : node.getAttribute('data-i18n-en') || fallback || '';
}

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return '0 B';
  }

  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size >= 10 || unitIndex === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[unitIndex]}`;
}

function getDownloadDetailText(receivedBytes, totalBytes, isEstimated) {
  const language = getLanguage();
  if (totalBytes > 0) {
    return language === 'zh'
      ? `已接收 ${formatBytes(receivedBytes)} / ${formatBytes(totalBytes)}`
      : `${formatBytes(receivedBytes)} of ${formatBytes(totalBytes)} received`;
  }

  if (isEstimated) {
    return language === 'zh'
      ? `已接收 ${formatBytes(receivedBytes)}，总大小未知，前端估算进度中`
      : `${formatBytes(receivedBytes)} received, total size unknown, estimating progress locally`;
  }

  return language === 'zh'
    ? `已接收 ${formatBytes(receivedBytes)}`
    : `${formatBytes(receivedBytes)} received`;
}

function getDownloadSpeedText(bytesPerSecond) {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) {
    return '';
  }

  const language = getLanguage();
  return language === 'zh'
    ? `${formatBytes(bytesPerSecond)}/秒`
    : `${formatBytes(bytesPerSecond)}/s`;
}

function triggerBrowserDownload(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename || 'download';
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(function () {
    URL.revokeObjectURL(objectUrl);
  }, 1000);
}

function getFilenameFromDisposition(headerValue, fallback) {
  if (!headerValue) {
    return fallback || 'download';
  }

  const utf8Match = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match && utf8Match[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const basicMatch = headerValue.match(/filename="?([^";]+)"?/i);
  if (basicMatch && basicMatch[1]) {
    return basicMatch[1];
  }

  return fallback || 'download';
}

function initLogDownloadConsole() {
  const consoleNode = document.querySelector('[data-log-download-console]');
  const downloadLinks = document.querySelectorAll('[data-log-download]');
  if (!consoleNode || !downloadLinks.length) {
    return;
  }

  const percentNode = consoleNode.querySelector('[data-download-percent]');
  const fileNode = consoleNode.querySelector('[data-download-file]');
  const statusNode = consoleNode.querySelector('[data-download-status]');
  const detailNode = consoleNode.querySelector('[data-download-detail]');
  const speedNode = consoleNode.querySelector('[data-download-speed]');
  const barNode = consoleNode.querySelector('[data-download-bar]');
  const progressNode = consoleNode.querySelector('.console-progress');
  let activeController = null;

  function updateProgress(progressValue) {
    const safeProgress = Math.max(0, Math.min(100, Math.round(progressValue)));
    barNode.style.width = `${safeProgress}%`;
    percentNode.textContent = `${safeProgress}%`;
    progressNode.setAttribute('aria-valuenow', String(safeProgress));
  }

  function setStatus(statusText, detailText, speedText) {
    statusNode.textContent = statusText;
    detailNode.textContent = detailText;
    speedNode.textContent = speedText || '';
  }

  async function handleDownload(event) {
    event.preventDefault();

    const link = event.currentTarget;
    const downloadUrl = link.href;
    const fallbackFilename = link.getAttribute('data-log-filename') || 'download.log';
    const language = getLanguage();

    if (activeController) {
      activeController.abort();
    }

    const controller = new AbortController();
    activeController = controller;
    consoleNode.classList.remove('is-hidden');
    fileNode.textContent = fallbackFilename;
    updateProgress(0);
    setStatus(
      language === 'zh' ? '开始下载...' : 'Starting download...',
      getI18nText(detailNode, 'No active download.'),
      ''
    );

    try {
      const response = await fetch(downloadUrl, {
        credentials: 'same-origin',
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        const blob = await response.blob();
        triggerBrowserDownload(blob, fallbackFilename);
        updateProgress(100);
        setStatus(
          language === 'zh' ? '下载完成' : 'Download complete',
          language === 'zh' ? '浏览器未提供流式进度，已在完成后保存文件。' : 'The browser did not expose stream progress, file saved after completion.',
          ''
        );
        return;
      }

      const totalBytes = Number(response.headers.get('Content-Length') || '0');
      const filename = getFilenameFromDisposition(response.headers.get('Content-Disposition'), fallbackFilename);
      const reader = response.body.getReader();
      const chunks = [];
      let receivedBytes = 0;
      const startTime = performance.now();
      let estimatedProgress = 0;

      fileNode.textContent = filename;
      setStatus(
        language === 'zh' ? '下载中...' : 'Downloading...',
        getDownloadDetailText(receivedBytes, totalBytes, totalBytes <= 0),
        ''
      );

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        chunks.push(value);
        receivedBytes += value.byteLength;
        const elapsedSeconds = Math.max((performance.now() - startTime) / 1000, 0.001);
        const bytesPerSecond = receivedBytes / elapsedSeconds;

        if (totalBytes > 0) {
          updateProgress((receivedBytes / totalBytes) * 100);
        } else {
          estimatedProgress = Math.min(95, estimatedProgress + Math.max(3, Math.min(12, elapsedSeconds * 4)));
          updateProgress(estimatedProgress);
        }

        setStatus(
          language === 'zh' ? '下载中...' : 'Downloading...',
          getDownloadDetailText(receivedBytes, totalBytes, totalBytes <= 0),
          getDownloadSpeedText(bytesPerSecond)
        );
      }

      const blob = new Blob(chunks);
      triggerBrowserDownload(blob, filename);
      updateProgress(100);
      setStatus(
        language === 'zh' ? '下载完成' : 'Download complete',
        language === 'zh' ? `已保存 ${formatBytes(receivedBytes)}` : `Saved ${formatBytes(receivedBytes)}`,
        getDownloadSpeedText(receivedBytes / Math.max((performance.now() - startTime) / 1000, 0.001))
      );
    } catch (error) {
      if (error.name === 'AbortError') {
        setStatus(
          language === 'zh' ? '已取消之前的下载' : 'Previous download cancelled',
          language === 'zh' ? '新的下载请求已接管进度面板。' : 'A new download request took over the progress panel.',
          ''
        );
        return;
      }

      updateProgress(0);
      setStatus(
        language === 'zh' ? '下载失败' : 'Download failed',
        language === 'zh' ? `请求未完成：${error.message}` : `Request did not complete: ${error.message}`,
        ''
      );
    } finally {
      if (activeController === controller) {
        activeController = null;
      }
    }
  }

  downloadLinks.forEach(function (link) {
    link.addEventListener('click', handleDownload);
  });
}

const savedTheme = localStorage.getItem('theme') || 'light';
const savedLanguage = localStorage.getItem('language') || 'en';
const themeInput = document.querySelector(`input[value="${savedTheme}"]`);
if (themeInput) {
  themeInput.checked = true;
}
setTheme(savedTheme);
applyLanguage(savedLanguage);

document.querySelectorAll('input[name="theme"]').forEach(function (radio) {
  radio.addEventListener('change', function () {
    const selectedTheme = this.value;
    localStorage.setItem('theme', selectedTheme);
    setTheme(selectedTheme);
  });
});

document.querySelectorAll('[data-language-toggle]').forEach(function (button) {
  button.addEventListener('click', function () {
    const selectedLanguage = this.getAttribute('data-language-toggle') || 'en';
    localStorage.setItem('language', selectedLanguage);
    applyLanguage(selectedLanguage);
  });
});

initLogDownloadConsole();

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
  if (localStorage.getItem('theme') === 'auto') {
    setTheme('auto');
  }
});
