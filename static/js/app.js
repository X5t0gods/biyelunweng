/**
 * 系统公共脚本
 */
(function () {
    'use strict';

    // 删除确认
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            if (!window.confirm(el.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

    // 表格全选
    document.querySelectorAll('[data-check-all]').forEach(function (master) {
        master.addEventListener('change', function () {
            var target = master.getAttribute('data-check-all');
            document.querySelectorAll('input[name="' + target + '"]').forEach(function (box) {
                box.checked = master.checked;
            });
        });
    });
})();

/**
 * 金额格式化
 */
function fmtMoney(value) {
    var n = parseFloat(value || 0);
    return '¥' + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}
