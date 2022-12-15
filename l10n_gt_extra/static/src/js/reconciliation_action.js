odoo.define('l1on_gt_extra.ReconciliationClientActionGTExtra', function(require) {
    "use strict";

    var StatementAction = require('account.ReconciliationClientAction');
    var ReconciliationModel = require('account.ReconciliationModel');
    var ReconciliationRenderer = require('account.ReconciliationRenderer');
    var core = require('web.core');
    var QWeb = core.qweb;

    StatementAction.StatementAction.include({
        /**
         * render line widget and append to view
         *
         * @private
         */
        _renderLines: function() {

            this.$('.validate_all_lines').click(function() {
                var reconcile_found = false;
                $("button.o_reconcile").each(function() {

                    if (!$(this).hasClass('d-none')) {
                        reconcile_found = true
                        var self = this;
                        setTimeout(function() {
                            $(self).click();
                        }, 200);
                    }

                });
                $("button.o_validate").each(function() {

                    if (!$(this).hasClass('d-none')) {
                        reconcile_found = true
                        var self = this;
                        setTimeout(function() {
                            $(self).click();
                        }, 200);
                    }

                });
                if (!reconcile_found) {
                    alert('No se encontró ninguna extracto a validar');
                }
            });
            return this._super.apply(this, arguments);

        },
    });
});