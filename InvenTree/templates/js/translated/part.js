{% load i18n %}
{% load inventree_extras %}

/* globals
    Chart,
    constructForm,
    global_settings,
    imageHoverIcon,
    inventreeGet,
    inventreePut,
    launchModalForm,
    linkButtonsToSelection,
    loadTableFilters,
    makeIconBadge,
    makeIconButton,
    printPartLabels,
    renderLink,
    setFormGroupVisibility,
    setupFilterList,
    yesNoLabel,
*/

/* exported
    duplicateBom,
    duplicatePart,
    editCategory,
    editPart,
    initPriceBreakSet,
    loadBomChart,
    loadParametricPartTable,
    loadPartCategoryTable,
    loadPartParameterTable,
    loadPartPurchaseOrderTable,
    loadPartTable,
    loadPartTestTemplateTable,
    loadPartSchedulingChart,
    loadPartVariantTable,
    loadRelatedPartsTable,
    loadSellPricingChart,
    loadSimplePartTable,
    loadStockPricingChart,
    partStockLabel,
    toggleStar,
    validateBom,
*/

/* Part API functions
 * Requires api.js to be loaded first
 */

function partGroups() {

    return {
        attributes: {
            title: '{% trans "Part Attributes" %}',
            collapsible: true,
        },
        create: {
            title: '{% trans "Part Creation Options" %}',
            collapsible: true,
        },
        duplicate: {
            title: '{% trans "Part Duplication Options" %}',
            collapsible: true,
        },
        supplier: {
            title: '{% trans "Supplier Options" %}',
            collapsible: true,
            hidden: !global_settings.PART_PURCHASEABLE,
        }
    };
}


// Construct fieldset for part forms
function partFields(options={}) {

    var fields = {
        category: {
            secondary: {
                title: '{% trans "Add Part Category" %}',
                fields: function() {
                    var fields = categoryFields();

                    return fields;
                }
            }
        },
        name: {},
        IPN: {},
        revision: {},
        description: {},
        variant_of: {},
        keywords: {
            icon: 'fa-key',
        },
        units: {},
        link: {
            icon: 'fa-link',
        },
        default_location: {
        },
        default_supplier: {
            filters: {
                part_detail: true,
                supplier_detail: true,
            }
        },
        default_expiry: {
            icon: 'fa-calendar-alt',
        },
        minimum_stock: {
            icon: 'fa-boxes',
        },
        component: {
            default: global_settings.PART_COMPONENT,
            group: 'attributes',
        },
        assembly: {
            default: global_settings.PART_ASSEMBLY,
            group: 'attributes',
        },
        is_template: {
            default: global_settings.PART_TEMPLATE,
            group: 'attributes',
        },
        trackable: {
            default: global_settings.PART_TRACKABLE,
            group: 'attributes',
        },
        purchaseable: {
            default: global_settings.PART_PURCHASEABLE,
            group: 'attributes',
            onEdit: function(value, name, field, options) {
                setFormGroupVisibility('supplier', value, options);
            }
        },
        salable: {
            default: global_settings.PART_SALABLE,
            group: 'attributes',
        },
        virtual: {
            default: global_settings.PART_VIRTUAL,
            group: 'attributes',
        },
    };

    // If editing a part, we can set the "active" status
    if (options.edit) {
        fields.active = {
            group: 'attributes'
        };
    }

    // Pop expiry field
    if (!global_settings.STOCK_ENABLE_EXPIRY) {
        delete fields['default_expiry'];
    }

    if (options.create || options.duplicate) {
        if (global_settings.PART_CREATE_INITIAL) {

            fields.initial_stock = {
                type: 'boolean',
                label: '{% trans "Create Initial Stock" %}',
                help_text: '{% trans "Create an initial stock item for this part" %}',
                group: 'create',
            };

            fields.initial_stock_quantity = {
                type: 'decimal',
                value: 1,
                label: '{% trans "Initial Stock Quantity" %}',
                help_text: '{% trans "Specify initial stock quantity for this part" %}',
                group: 'create',
            };

            // TODO - Allow initial location of stock to be specified
            fields.initial_stock_location = {
                label: '{% trans "Location" %}',
                help_text: '{% trans "Select destination stock location" %}',
                type: 'related field',
                required: true,
                api_url: `/api/stock/location/`,
                model: 'stocklocation',
                group: 'create',
            };
        }
    }

    // Additional fields when "creating" a new part
    if (options.create) {

        // No supplier parts available yet
        delete fields['default_supplier'];

        fields.copy_category_parameters = {
            type: 'boolean',
            label: '{% trans "Copy Category Parameters" %}',
            help_text: '{% trans "Copy parameter templates from selected part category" %}',
            value: global_settings.PART_CATEGORY_PARAMETERS,
            group: 'create',
        };

        // Supplier options
        fields.add_supplier_info = {
            type: 'boolean',
            label: '{% trans "Add Supplier Data" %}',
            help_text: '{% trans "Create initial supplier data for this part" %}',
            group: 'supplier',
        };
        
        fields.supplier = {
            type: 'related field',
            model: 'company',
            label: '{% trans "Supplier" %}',
            help_text: '{% trans "Select supplier" %}',
            filters: {
                'is_supplier': true,
            },
            api_url: '{% url "api-company-list" %}',
            group: 'supplier',
        };
        
        fields.SKU = {
            type: 'string',
            label: '{% trans "SKU" %}', 
            help_text: '{% trans "Supplier stock keeping unit" %}',
            group: 'supplier',
        };
        
        fields.manufacturer = {
            type: 'related field',
            model: 'company',
            label: '{% trans "Manufacturer" %}',
            help_text: '{% trans "Select manufacturer" %}',
            filters: {
                'is_manufacturer': true,
            },
            api_url: '{% url "api-company-list" %}',
            group: 'supplier',
        };
        
        fields.MPN = {
            type: 'string',
            label: '{% trans "MPN" %}',
            help_text: '{% trans "Manufacturer Part Number" %}',
            group: 'supplier',
        };

    }

    // Additional fields when "duplicating" a part
    if (options.duplicate) {

        fields.copy_from = {
            type: 'integer',
            hidden: true,
            value: options.duplicate,
            group: 'duplicate',
        },

        fields.copy_image = {
            type: 'boolean',
            label: '{% trans "Copy Image" %}',
            help_text: '{% trans "Copy image from original part" %}',
            value: true,
            group: 'duplicate',
        },

        fields.copy_bom = {
            type: 'boolean',
            label: '{% trans "Copy BOM" %}',
            help_text: '{% trans "Copy bill of materials from original part" %}',
            value: global_settings.PART_COPY_BOM,
            group: 'duplicate',
        };

        fields.copy_parameters = {
            type: 'boolean',
            label: '{% trans "Copy Parameters" %}',
            help_text: '{% trans "Copy parameter data from original part" %}',
            value: global_settings.PART_COPY_PARAMETERS,
            group: 'duplicate',
        };
    }

    return fields;
}


function categoryFields() {
    return {
        parent: {
            help_text: '{% trans "Parent part category" %}',
            required: false,
        },
        name: {},
        description: {},
        default_location: {},
        default_keywords: {
            icon: 'fa-key',
        }
    };
}


// Edit a PartCategory via the API
function editCategory(pk) {

    var url = `/api/part/category/${pk}/`;

    var fields = categoryFields();

    constructForm(url, {
        fields: fields,
        title: '{% trans "Edit Part Category" %}',
        reload: true,
    });

}


function editPart(pk) {

    var url = `/api/part/${pk}/`;

    var fields = partFields({
        edit: true
    });

    // Filter supplied parts by the Part ID
    fields.default_supplier.filters.part = pk;

    var groups = partGroups({});

    constructForm(url, {
        fields: fields,
        groups: groups,
        title: '{% trans "Edit Part" %}',
        reload: true,
        successMessage: '{% trans "Part edited" %}',
    });
}


// Launch form to duplicate a part
function duplicatePart(pk, options={}) {

    var title = '{% trans "Duplicate Part" %}';

    if (options.variant) {
        title = '{% trans "Create Part Variant" %}';
    }

    // First we need all the part information
    inventreeGet(`/api/part/${pk}/`, {}, {

        success: function(data) {
            
            var fields = partFields({
                duplicate: pk,
            });

            if (fields.initial_stock_location) {
                fields.initial_stock_location.value = data.default_location;
            }

            // Remove "default_supplier" field
            delete fields['default_supplier'];

            // If we are making a "variant" part
            if (options.variant) {

                // Override the "variant_of" field
                data.variant_of = pk;

                // By default, disable "is_template" when making a variant *of* a template
                data.is_template = false;
            }
            
            constructForm('{% url "api-part-list" %}', {
                method: 'POST',
                fields: fields,
                groups: partGroups(),
                title: title,
                data: data,
                onSuccess: function(data) {
                    // Follow the new part
                    location.href = `/part/${data.pk}/`;
                }
            });
        }
    });
}


/* Toggle the 'starred' status of a part.
 * Performs AJAX queries and updates the display on the button.
 * 
 * options:
 * - button: ID of the button (default = '#part-star-icon')
 * - URL: API url of the object
 * - user: pk of the user
 */
function toggleStar(options) {

    inventreeGet(options.url, {}, {
        success: function(response) {

            var starred = response.starred;

            inventreePut(
                options.url,
                {
                    starred: !starred,
                },
                {
                    method: 'PATCH',
                    success: function(response) {
                        if (response.starred) {
                            $(options.button).removeClass('fa fa-bell-slash').addClass('fas fa-bell icon-green');
                            $(options.button).attr('title', '{% trans "You are subscribed to notifications for this item" %}');

                            showMessage('{% trans "You have subscribed to notifications for this item" %}', {
                                style: 'success',
                            });
                        } else {
                            $(options.button).removeClass('fas fa-bell icon-green').addClass('fa fa-bell-slash');
                            $(options.button).attr('title', '{% trans "Subscribe to notifications for this item" %}');

                            showMessage('{% trans "You have unsubscribed to notifications for this item" %}', {
                                style: 'warning',
                            });
                        }
                    }
                }
            );
        }
    });
}


/* Validate a BOM */
function validateBom(part_id, options={}) {

    var html = `
    <div class='alert alert-block alert-success'>
    {% trans "Validating the BOM will mark each line item as valid" %}
    </div>
    `;

    constructForm(`/api/part/${part_id}/bom-validate/`, {
        method: 'PUT',
        fields: {
            valid: {},
        },
        preFormContent: html,
        title: '{% trans "Validate Bill of Materials" %}',
        reload: options.reload,
        onSuccess: function(response) {
            showMessage('{% trans "Validated Bill of Materials" %}');
        }
    });
}


/* Duplicate a BOM */
function duplicateBom(part_id, options={}) {

    constructForm(`/api/part/${part_id}/bom-copy/`, {
        method: 'POST',
        fields: {
            part: {
                icon: 'fa-shapes',
                filters: {
                    assembly: true,
                    exclude_tree: part_id,
                }
            },
            include_inherited: {},
            copy_substitutes: {},
            remove_existing: {},
            skip_invalid: {},
        },
        confirm: true,
        title: '{% trans "Copy Bill of Materials" %}',
        onSuccess: function(response) {
            if (options.success) {
                options.success(response);
            }
        },
    });

}


/*
 * Construct a "badge" label showing stock information for this particular part
 */
function partStockLabel(part, options={}) {

    // Prevent literal string 'null' from being displayed
    if (part.units == null) {
        part.units = '';
    }

    if (part.in_stock) {
        // There IS stock available for this part

        // Is stock "low" (below the 'minimum_stock' quantity)?
        if ((part.minimum_stock > 0) && (part.minimum_stock > part.in_stock)) {
            return `<span class='badge rounded-pill bg-warning ${options.classes}'>{% trans "Low stock" %}: ${part.in_stock}${part.units}</span>`;
        } else if (part.unallocated_stock == 0) {
            if (part.ordering) {
                // There is no available stock, but stock is on order
                return `<span class='badge rounded-pill bg-info ${options.classes}'>{% trans "On Order" %}: ${part.ordering}${part.units}</span>`;
            } else if (part.building) {
                // There is no available stock, but stock is being built
                return `<span class='badge rounded-pill bg-info ${options.classes}'>{% trans "Building" %}: ${part.building}${part.units}</span>`;
            } else {
                // There is no available stock at all
                return `<span class='badge rounded-pill bg-warning ${options.classes}'>{% trans "No stock available" %}</span>`;
            }
        } else if (part.unallocated_stock < part.in_stock) {
            // Unallocated quanttiy is less than total quantity
            return `<span class='badge rounded-pill bg-success ${options.classes}'>{% trans "Available" %}: ${part.unallocated_stock}/${part.in_stock}${part.units}</span>`;
        } else {
            // Stock is completely available
            return `<span class='badge rounded-pill bg-success ${options.classes}'>{% trans "Available" %}: ${part.unallocated_stock}${part.units}</span>`;
        }
    } else {
        // There IS NO stock available for this part

        if (part.ordering) {
            // There is no stock, but stock is on order
            return `<span class='badge rounded-pill bg-info ${options.classes}'>{% trans "On Order" %}: ${part.ordering}${part.units}</span>`;
        } else if (part.building) {
            // There is no stock, but stock is being built
            return `<span class='badge rounded-pill bg-info ${options.classes}'>{% trans "Building" %}: ${part.building}${part.units}</span>`;
        } else {
            // There is no stock
            return `<span class='badge rounded-pill bg-danger ${options.classes}'>{% trans "No Stock" %}</span>`;
        }
    }

}


function makePartIcons(part) {
    /* Render a set of icons for the given part.
     */

    var html = '';

    if (part.trackable) {
        html += makeIconBadge('fa-directions', '{% trans "Trackable part" %}');
    }

    if (part.virtual) {
        html += makeIconBadge('fa-ghost', '{% trans "Virtual part" %}');
    }

    if (part.is_template) {
        html += makeIconBadge('fa-clone', '{% trans "Template part" %}');
    }

    if (part.assembly) {
        html += makeIconBadge('fa-tools', '{% trans "Assembled part" %}');
    }

    if (part.starred) {
        html += makeIconBadge('fa-bell icon-green', '{% trans "Subscribed part" %}');
    }

    if (part.salable) {
        html += makeIconBadge('fa-dollar-sign', '{% trans "Salable part" %}');
    }

    if (!part.active) {
        html += `<span class='badge badge-right rounded-pill bg-warning'>{% trans "Inactive" %}</span> `; 
    }

    return html;

}


function loadPartVariantTable(table, partId, options={}) {
    /* Load part variant table
     */

    var params = options.params || {};

    params.ancestor = partId;

    // Load filters
    var filters = loadTableFilters('variants');

    for (var key in params) {
        filters[key] = params[key];
    }

    setupFilterList('variants', $(table));

    var cols = [
        {
            field: 'pk',
            title: 'ID',
            visible: false,
            switchable: false,
        },
        {
            field: 'name',
            title: '{% trans "Name" %}',
            switchable: false,
            formatter: function(value, row) {
                var html = '';

                var name = '';

                if (row.IPN) {
                    name += row.IPN;
                    name += ' | ';
                }

                name += value;

                if (row.revision) {
                    name += ' | ';
                    name += row.revision;
                }

                if (row.is_template) {
                    name = '<i>' + name + '</i>';
                }

                html += imageHoverIcon(row.thumbnail);
                html += renderLink(name, `/part/${row.pk}/`);

                if (row.trackable) {
                    html += makeIconBadge('fa-directions', '{% trans "Trackable part" %}');
                }

                if (row.virtual) {
                    html += makeIconBadge('fa-ghost', '{% trans "Virtual part" %}');
                }

                if (row.is_template) {
                    html += makeIconBadge('fa-clone', '{% trans "Template part" %}');
                }

                if (row.assembly) {
                    html += makeIconBadge('fa-tools', '{% trans "Assembled part" %}');
                }

                if (!row.active) {
                    html += `<span class='badge badge-right rounded-pill bg-warning'>{% trans "Inactive" %}</span>`; 
                }

                return html;
            },
        },
        {
            field: 'IPN',
            title: '{% trans "IPN" %}',
        },
        {
            field: 'revision',
            title: '{% trans "Revision" %}',
        },
        {
            field: 'description',
            title: '{% trans "Description" %}',
        },
        {
            field: 'in_stock',
            title: '{% trans "Stock" %}',
            formatter: function(value, row) {

                var base_stock = row.in_stock;
                var variant_stock = row.variant_stock || 0;

                var total = base_stock + variant_stock;

                var text = `${total}`;

                if (variant_stock > 0) {
                    text = `<em>${text}</em>`;
                    text += `<span title='{% trans "Includes variant stock" %}' class='fas fa-info-circle float-right icon-blue'></span>`;
                }

                return renderLink(text, `/part/${row.pk}/?display=part-stock`);
            }
        }
    ];

    table.inventreeTable({
        url: '{% url "api-part-list" %}',
        name: 'partvariants',
        showColumns: true,
        original: params,
        queryParams: filters,
        formatNoMatches: function() {
            return '{% trans "No variants found" %}';
        },
        columns: cols,
        treeEnable: true,
        rootParentId: partId,
        parentIdField: 'variant_of',
        idField: 'pk',
        uniqueId: 'pk',
        treeShowField: 'name',
        sortable: true,
        search: true,
        onPostBody: function() {
            table.treegrid({
                treeColumn: 0,
            });

            table.treegrid('collapseAll');
        }
    });
}


function loadSimplePartTable(table, url, options={}) {

    options.disableFilters = true;

    loadPartTable(table, url, options);
}


function loadPartParameterTable(table, url, options) {

    var params = options.params || {};

    // Load filters
    var filters = loadTableFilters('part-parameters');

    for (var key in params) {
        filters[key] = params[key];
    }

    var filterTarget = options.filterTarget || '#filter-list-parameters';

    setupFilterList('part-parameters', $(table), filterTarget);

    $(table).inventreeTable({
        url: url,
        original: params,
        queryParams: filters,
        name: 'partparameters',
        groupBy: false,
        formatNoMatches: function() {
            return '{% trans "No parameters found" %}';
        },
        columns: [
            {
                checkbox: true,
                switchable: false,
                visible: true,
            },
            {
                field: 'name',
                title: '{% trans "Name" %}',
                switchable: false,
                sortable: true,
                formatter: function(value, row) {
                    return row.template_detail.name;
                }
            },
            {
                field: 'data',
                title: '{% trans "Value" %}',
                switchable: false,
                sortable: true,
            },
            {
                field: 'units',
                title: '{% trans "Units" %}',
                switchable: true,
                sortable: true,
                formatter: function(value, row) {
                    return row.template_detail.units;
                }
            },
            {
                field: 'actions',
                title: '',
                switchable: false,
                sortable: false,
                formatter: function(value, row) {
                    var pk = row.pk;

                    var html = `<div class='btn-group float-right' role='group'>`;

                    html += makeIconButton('fa-edit icon-blue', 'button-parameter-edit', pk, '{% trans "Edit parameter" %}');
                    html += makeIconButton('fa-trash-alt icon-red', 'button-parameter-delete', pk, '{% trans "Delete parameter" %}');

                    html += `</div>`;

                    return html;
                }
            }
        ],
        onPostBody: function() {
            // Setup button callbacks
            $(table).find('.button-parameter-edit').click(function() {
                var pk = $(this).attr('pk');

                constructForm(`/api/part/parameter/${pk}/`, {
                    fields: {
                        data: {},
                    },
                    title: '{% trans "Edit Parameter" %}',
                    onSuccess: function() {
                        $(table).bootstrapTable('refresh');
                    }
                });
            });

            $(table).find('.button-parameter-delete').click(function() {
                var pk = $(this).attr('pk');

                constructForm(`/api/part/parameter/${pk}/`, {
                    method: 'DELETE',
                    title: '{% trans "Delete Parameter" %}',
                    onSuccess: function() {
                        $(table).bootstrapTable('refresh');
                    }
                });
            });
        }
    });
}


/*
 * Construct a table showing a list of purchase orders for a given part.
 * 
 * This requests API data from the PurchaseOrderLineItem endpoint
 */
function loadPartPurchaseOrderTable(table, part_id, options={}) {

    options.params = options.params || {};

    // Construct API filterset
    options.params.base_part = part_id;
    options.params.part_detail = true;
    options.params.order_detail = true;
    
    var filters = loadTableFilters('purchaseorderlineitem');

    for (var key in options.params) {
        filters[key] = options.params[key];
    }

    setupFilterList('purchaseorderlineitem', $(table), '#filter-list-partpurchaseorders');

    $(table).inventreeTable({
        url: '{% url "api-po-line-list" %}',
        queryParams: filters,
        name: 'partpurchaseorders',
        original: options.params,
        showColumns: true,
        uniqueId: 'pk',
        formatNoMatches: function() {
            return '{% trans "No purchase orders found" %}';
        },
        onPostBody: function() {
            $(table).find('.button-line-receive').click(function() {
                var pk = $(this).attr('pk');

                var line_item = $(table).bootstrapTable('getRowByUniqueId', pk);

                if (!line_item) {
                    console.log('WARNING: getRowByUniqueId returned null');
                    return;
                }

                receivePurchaseOrderItems(
                    line_item.order,
                    [
                        line_item,
                    ],
                    {
                        success: function() {
                            $(table).bootstrapTable('refresh');
                        }
                    }
                );
            });
        },
        columns: [
            {
                field: 'order',
                title: '{% trans "Purchase Order" %}',
                switchable: false,
                formatter: function(value, row) {
                    var order = row.order_detail;

                    if (!order) {
                        return '-';
                    }

                    var ref = global_settings.PURCHASEORDER_REFERENCE_PREFIX + order.reference;

                    var html = renderLink(ref, `/order/purchase-order/${order.pk}/`);

                    html += purchaseOrderStatusDisplay(
                        order.status,
                        {
                            classes: 'float-right',
                        }
                    );

                    return html;
                },
            },
            {
                field: 'supplier',
                title: '{% trans "Supplier" %}',
                switchable: true,
                formatter: function(value, row) {

                    if (row.supplier_part_detail && row.supplier_part_detail.supplier_detail) {
                        var supp = row.supplier_part_detail.supplier_detail;
                        var html = imageHoverIcon(supp.thumbnail || supp.image);

                        html += ' ' + renderLink(supp.name, `/company/${supp.pk}/`);

                        return html;
                    } else {
                        return '-';
                    }
                }
            },
            {
                field: 'sku',
                title: '{% trans "SKU" %}',
                switchable: true,
                formatter: function(value, row) {
                    if (row.supplier_part_detail) {
                        var supp = row.supplier_part_detail;

                        return renderLink(supp.SKU, `/supplier-part/${supp.pk}/`);
                    } else {
                        return '-';
                    }
                },
            },
            {
                field: 'mpn',
                title: '{% trans "MPN" %}',
                switchable: true,
                formatter: function(value, row) {
                    if (row.supplier_part_detail && row.supplier_part_detail.manufacturer_part_detail) {
                        var manu = row.supplier_part_detail.manufacturer_part_detail;
                        return renderLink(manu.MPN, `/manufacturer-part/${manu.pk}/`);
                    }
                }
            },
            {
                field: 'quantity',
                title: '{% trans "Quantity" %}',
            },
            {
                field: 'target_date',
                title: '{% trans "Target Date" %}',
                switchable: true,
                sortable: true,
                formatter: function(value, row) {
                    if (row.target_date) {
                        var html = row.target_date;

                        if (row.overdue) {
                            html += `<span class='fas fa-calendar-alt icon-red float-right' title='{% trans "This line item is overdue" %}'></span>`;
                        }

                        return html;

                    } else if (row.order_detail && row.order_detail.target_date) {
                        return `<em>${row.order_detail.target_date}</em>`;
                    } else {
                        return '-';
                    }
                }
            },
            {
                field: 'received',
                title: '{% trans "Received" %}',
                switchable: true,
            },
            {
                field: 'purchase_price',
                title: '{% trans "Price" %}',
                switchable: true,
                formatter: function(value, row) {
                    var formatter = new Intl.NumberFormat(
                        'en-US',
                        {
                            style: 'currency',
                            currency: row.purchase_price_currency,
                        }
                    );

                    return formatter.format(row.purchase_price);
                }
            },
            {
                field: 'actions',
                title: '',
                switchable: false,
                formatter: function(value, row) {
                    
                    if (row.received >= row.quantity) {
                        // Already recevied
                        return `<span class='badge bg-success rounded-pill'>{% trans "Received" %}</span>`;
                    } else if (row.order_detail && row.order_detail.status == {{ PurchaseOrderStatus.PLACED }}) {
                        var html = `<div class='btn-group' role='group'>`;
                        var pk = row.pk;

                        html += makeIconButton('fa-sign-in-alt', 'button-line-receive', pk, '{% trans "Receive line item" %}');

                        html += `</div>`;
                        return html;
                    } else {
                        return '';
                    }
                }
            }
        ],
    });
}


function loadRelatedPartsTable(table, part_id, options={}) {
    /*
     * Load table of "related" parts
     */

    options.params = options.params || {};

    options.params.part = part_id;

    var filters = {};

    for (var key in options.params) {
        filters[key] = options.params[key];
    }

    setupFilterList('related', $(table), options.filterTarget);

    function getPart(row) {
        if (row.part_1 == part_id) {
            return row.part_2_detail;
        } else {
            return row.part_1_detail;
        }
    }

    var columns = [
        {
            field: 'name',
            title: '{% trans "Part" %}',
            switchable: false,
            formatter: function(value, row) {

                var part = getPart(row);

                var html = imageHoverIcon(part.thumbnail) + renderLink(part.full_name, `/part/${part.pk}/`);

                html += makePartIcons(part);

                return html;
            }
        },
        {
            field: 'description',
            title: '{% trans "Description" %}',
            formatter: function(value, row) {
                return getPart(row).description;
            }
        },
        {
            field: 'actions',
            title: '',
            switchable: false,
            formatter: function(value, row) {
                
                var html = `<div class='btn-group float-right' role='group'>`;

                html += makeIconButton('fa-trash-alt icon-red', 'button-related-delete', row.pk, '{% trans "Delete part relationship" %}');

                html += '</div>';

                return html;
            }
        }
    ];

    $(table).inventreeTable({
        url: '{% url "api-part-related-list" %}',
        groupBy: false,
        name: 'related',
        original: options.params,
        queryParams: filters,
        columns: columns,
        showColumns: false,
        search: true,
        onPostBody: function() {
            $(table).find('.button-related-delete').click(function() {
                var pk = $(this).attr('pk');

                constructForm(`/api/part/related/${pk}/`, {
                    method: 'DELETE',
                    title: '{% trans "Delete Part Relationship" %}',
                    onSuccess: function() {
                        $(table).bootstrapTable('refresh');
                    }
                });
            });
        },
    });
}


/* Load parametric table for part parameters
 */
function loadParametricPartTable(table, options={}) {

    var columns = [
        {
            field: 'name',
            title: '{% trans "Part" %}',
            switchable: false,
            sortable: true,
            formatter: function(value, row) {
                var name = row.full_name;

                var display = imageHoverIcon(row.thumbnail) + renderLink(name, `/part/${row.pk}/`);

                return display;
            }
        }
    ];

    // Request a list of parameters we are interested in for this category
    inventreeGet(
        '{% url "api-part-parameter-template-list" %}',
        {
            category: options.category,
        },
        {
            async: false,
            success: function(response) {
                for (var template of response) {
                    columns.push({
                        field: `parameter_${template.pk}`,
                        title: template.name,
                        switchable: true,
                        sortable: true,
                        filterControl: 'input',
                    });
                }
            }
        }
    );

    // TODO: Re-enable filter control for parameter values

    $(table).inventreeTable({
        url: '{% url "api-part-list" %}',
        queryParams: {
            category: options.category,
            cascade: true,
            parameters: true,
        },
        groupBy: false,
        name: options.name || 'part-parameters',
        formatNoMatches: function() {
            return '{% trans "No parts found" %}';
        },
        columns: columns,
        showColumns: true,
        // filterControl: true,
        sidePagination: 'server',
        idField: 'pk',
        uniqueId: 'pk',
        onLoadSuccess: function() {

            var data = $(table).bootstrapTable('getData');

            for (var idx = 0; idx < data.length; idx++) {
                var row = data[idx];
                var pk = row.pk;

                // Make each parameter accessible, based on the "template" columns
                row.parameters.forEach(function(parameter) {
                    row[`parameter_${parameter.template}`] = parameter.data;
                });

                $(table).bootstrapTable('updateRow', pk, row);
            }
        }
    });
}


function partGridTile(part) {
    // Generate a "grid tile" view for a particular part

    // Rows for table view
    var rows = '';

    var stock = `${part.in_stock}`;

    if (!part.in_stock) {
        stock = `<span class='badge rounded-pill bg-danger'>{% trans "No Stock" %}</span>`;
    } else if (!part.unallocated_stock) {
        stock = `<span class='badge rounded-pill bg-warning'>{% trans "Not available" %}</span>`;
    }

    rows += `<tr><td><b>{% trans "Stock" %}</b></td><td>${stock}</td></tr>`;

    if (part.ordering) {
        rows += `<tr><td><b>{% trans "On Order" %}</b></td><td>${part.ordering}</td></tr>`;
    }

    if (part.building) {
        rows += `<tr><td><b>{% trans "Building" %}</b></td><td>${part.building}</td></tr>`;
    }

    var html = `
    
    <div class='card product-card borderless'>
        <div class='panel product-card-panel'>
            <div class='panel-heading'>
                <a href='/part/${part.pk}/'>
                    <b>${part.full_name}</b>
                </a>
                ${makePartIcons(part)}
                <br>
                <i>${part.description}</i>
            </div>
            <div class='panel-content'>
                <div class='row'>
                    <div class='col-sm-6'>
                        <img src='${part.thumbnail}' class='card-thumb' onclick='showModalImage("${part.image}")'>
                    </div>
                    <div class='col-sm-6'>
                        <table class='table table-striped table-condensed'>
                            ${rows}
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>    
    `;

    return html;
}


function loadPartTable(table, url, options={}) {
    /* Load part listing data into specified table.
     * 
     * Args:
     *  - table: HTML reference to the table
     *  - url: Base URL for API query
     *  - options: object containing following (optional) fields
     *      checkbox: Show the checkbox column
     *      query: extra query params for API request
     *      buttons: If provided, link buttons to selection status of this table
     *      disableFilters: If true, disable custom filters
     *      actions: Provide a callback function to construct an "actions" column
     */

    // Ensure category detail is included
    options.params['category_detail'] = true;

    var params = options.params || {};

    var filters = {};

    var col = null;

    if (!options.disableFilters) {
        filters = loadTableFilters('parts');
    }

    for (var key in params) {
        filters[key] = params[key];
    }

    setupFilterList('parts', $(table), options.filterTarget, {download: true});

    var columns = [
        {
            field: 'pk',
            title: 'ID',
            visible: false,
            switchable: false,
            searchable: false,
        }
    ];

    if (options.checkbox) {
        columns.push({
            checkbox: true,
            title: '{% trans "Select" %}',
            searchable: false,
            switchable: false,
        });
    }

    col = {
        field: 'IPN',
        title: '{% trans "IPN" %}',
    };

    if (!options.params.ordering) {
        col['sortable'] = true;
    }

    columns.push(col);

    col = {
        field: 'name',
        title: '{% trans "Part" %}',
        switchable: false,
        formatter: function(value, row) {

            var name = row.full_name;

            var display = imageHoverIcon(row.thumbnail) + renderLink(name, `/part/${row.pk}/`);

            display += makePartIcons(row);

            return display; 
        }
    };

    if (!options.params.ordering) {
        col['sortable'] = true;
    }

    columns.push(col);

    columns.push({
        field: 'description',
        title: '{% trans "Description" %}',
        formatter: function(value, row) {

            if (row.is_template) {
                value = `<i>${value}</i>`;
            }

            return value;
        }
    });

    col = {
        sortName: 'category',
        field: 'category_detail',
        title: '{% trans "Category" %}',
        formatter: function(value, row) {
            if (row.category) {
                return renderLink(value.pathstring, `/part/category/${row.category}/`);
            } else {
                return '{% trans "No category" %}';
            }
        }   
    };

    if (!options.params.ordering) {
        col['sortable'] = true;
    }

    columns.push(col);

    col = {
        field: 'unallocated_stock',
        title: '{% trans "Stock" %}',
        searchable: false,
        formatter: function(value, row) {            
            var link = '?display=part-stock';

            if (row.in_stock) {
                // There IS stock available for this part

                // Is stock "low" (below the 'minimum_stock' quantity)?
                if (row.minimum_stock && row.minimum_stock > row.in_stock) {
                    value += `<span class='badge badge-right rounded-pill bg-warning'>{% trans "Low stock" %}</span>`;
                } else if (value == 0) {
                    if (row.ordering) {
                        // There is no available stock, but stock is on order
                        value = `0<span class='badge badge-right rounded-pill bg-info'>{% trans "On Order" %}: ${row.ordering}</span>`;
                        link = '?display=purchase-orders';
                    } else if (row.building) {
                        // There is no available stock, but stock is being built
                        value = `0<span class='badge badge-right rounded-pill bg-info'>{% trans "Building" %}: ${row.building}</span>`;
                        link = '?display=build-orders';
                    } else {
                        // There is no available stock
                        value = `0<span class='badge badge-right rounded-pill bg-warning'>{% trans "No stock available" %}</span>`;
                    }
                }
            } else {
                // There IS NO stock available for this part

                if (row.ordering) {
                    // There is no stock, but stock is on order
                    value = `0<span class='badge badge-right rounded-pill bg-info'>{% trans "On Order" %}: ${row.ordering}</span>`;
                    link = '?display=purchase-orders';
                } else if (row.building) {
                    // There is no stock, but stock is being built
                    value = `0<span class='badge badge-right rounded-pill bg-info'>{% trans "Building" %}: ${row.building}</span>`;
                    link = '?display=build-orders';
                } else {
                    // There is no stock
                    value = `0<span class='badge badge-right rounded-pill bg-danger'>{% trans "No Stock" %}</span>`;
                }
            }

            return renderLink(value, `/part/${row.pk}/${link}`);
        }
    };

    if (!options.params.ordering) {
        col['sortable'] = true;
    }

    columns.push(col);

    columns.push({
        field: 'link',
        title: '{% trans "Link" %}',
        formatter: function(value) {
            return renderLink(
                value, value,
                {
                    max_length: 32,
                    remove_http: true,
                }
            );
        }
    });

    // Push an "actions" column
    if (options.actions) {
        columns.push({
            field: 'actions',
            title: '',
            switchable: false,
            visible: true,
            searchable: false,
            sortable: false,
            formatter: function(value, row) {
                return options.actions(value, row);
            }
        });
    }

    var grid_view = options.gridView && inventreeLoad('part-grid-view') == 1;

    $(table).inventreeTable({
        url: url,
        method: 'get',
        queryParams: filters,
        groupBy: false,
        name: options.name || 'part',
        original: params,
        sidePagination: 'server',
        pagination: 'true',
        formatNoMatches: function() {
            return '{% trans "No parts found" %}';
        },
        columns: columns,
        showColumns: true,
        showCustomView: grid_view,
        showCustomViewButton: false,
        onPostBody: function() {
            grid_view = inventreeLoad('part-grid-view') == 1;
            if (grid_view) {
                $('#view-part-list').removeClass('btn-secondary').addClass('btn-outline-secondary');
                $('#view-part-grid').removeClass('btn-outline-secondary').addClass('btn-secondary');
            } else {
                $('#view-part-grid').removeClass('btn-secondary').addClass('btn-outline-secondary');
                $('#view-part-list').removeClass('btn-outline-secondary').addClass('btn-secondary');
            }

            if (options.onPostBody) {
                options.onPostBody();
            }
        },
        buttons: options.gridView ? [
            {
                icon: 'fas fa-bars',
                attributes: {
                    title: '{% trans "Display as list" %}',
                    id: 'view-part-list',
                },
                event: () => {
                    inventreeSave('part-grid-view', 0);
                    $(table).bootstrapTable(
                        'refreshOptions',
                        {
                            showCustomView: false,
                        }
                    );
                }
            },
            {
                icon: 'fas fa-th',
                attributes: {
                    title: '{% trans "Display as grid" %}',
                    id: 'view-part-grid',
                },
                event: () => {
                    inventreeSave('part-grid-view', 1);
                    $(table).bootstrapTable(
                        'refreshOptions',
                        {
                            showCustomView: true,
                        }
                    );
                }
            }
        ] : [],
        customView: function(data) {

            var html = '';

            html = `<div class='row full-height'>`;

            data.forEach(function(row, index) {
                
                // Force a new row every 5 columns
                if ((index > 0) && (index % 5 == 0) && (index < data.length)) {
                    html += `</div><div class='row full-height'>`;
                }

                html += partGridTile(row);
            });

            html += `</div>`;

            return html;
        }
    });
    
    if (options.buttons) {
        linkButtonsToSelection($(table), options.buttons);
    }

    /* Button callbacks for part table buttons */

    $('#multi-part-order').click(function() {
        var selections = $(table).bootstrapTable('getSelections');

        var parts = [];

        selections.forEach(function(item) {
            parts.push(item.pk);
        });

        launchModalForm('/order/purchase-order/order-parts/', {
            data: {
                parts: parts,
            },
        });
    });

    $('#multi-part-category').click(function() {
        var selections = $(table).bootstrapTable('getSelections');

        var parts = [];

        selections.forEach(function(item) {
            parts.push(item.pk);
        });

        launchModalForm('/part/set-category/', {
            data: {
                parts: parts,
            },
            reload: true,
        });
    });

    $('#multi-part-print-label').click(function() {
        var selections = $(table).bootstrapTable('getSelections');

        var items = [];

        selections.forEach(function(item) {
            items.push(item.pk);
        });

        printPartLabels(items);
    });

    $('#multi-part-export').click(function() {
        var selections = $(table).bootstrapTable('getSelections');

        var parts = '';

        selections.forEach(function(item) {
            parts += item.pk;
            parts += ',';
        });

        location.href = '/part/export/?parts=' + parts;
    });
}


/*
 * Display a table of part categories
 */
function loadPartCategoryTable(table, options) {

    var params = options.params || {};

    var filterListElement = options.filterList || '#filter-list-category';

    var filters = {};

    var filterKey = options.filterKey || options.name || 'category';

    if (!options.disableFilters) {
        filters = loadTableFilters(filterKey);
    }

    
    var tree_view = options.allowTreeView && inventreeLoad('category-tree-view') == 1;

    if (tree_view) {
        params.cascade = true;   
    }

    var original = {};

    for (var key in params) {
        original[key] = params[key];
        filters[key] = params[key];
    }

    setupFilterList(filterKey, table, filterListElement);

    table.inventreeTable({
        treeEnable: tree_view,
        rootParentId: tree_view ? options.params.parent : null,
        uniqueId: 'pk',
        idField: 'pk',
        treeShowField: 'name',
        parentIdField: tree_view ? 'parent' : null,
        method: 'get',
        url: options.url || '{% url "api-part-category-list" %}',
        queryParams: filters,
        disablePagination: tree_view,
        sidePagination: tree_view ? 'client' : 'server',
        serverSort: !tree_view, 
        search: !tree_view,
        name: 'category',
        original: original,
        showColumns: true,
        buttons: options.allowTreeView ? [
            {
                icon: 'fas fa-bars',
                attributes: {
                    title: '{% trans "Display as list" %}',
                    id: 'view-category-list',
                },
                event: () => {
                    inventreeSave('category-tree-view', 0);
                    table.bootstrapTable(
                        'refreshOptions',
                        {
                            treeEnable: false,
                            serverSort: true,
                            search: true,
                            pagination: true,
                        }
                    );
                }
            },
            {
                icon: 'fas fa-sitemap',
                attributes: {
                    title: '{% trans "Display as tree" %}',
                    id: 'view-category-tree',
                },
                event: () => {
                    inventreeSave('category-tree-view', 1);
                    table.bootstrapTable(
                        'refreshOptions',
                        {
                            treeEnable: true,
                            serverSort: false,
                            search: false,
                            pagination: false,
                        }
                    );
                }
            }
        ] : [],
        onPostBody: function() {

            if (options.allowTreeView) {

                tree_view = inventreeLoad('category-tree-view') == 1;

                if (tree_view) {

                    $('#view-category-list').removeClass('btn-secondary').addClass('btn-outline-secondary');
                    $('#view-category-tree').removeClass('btn-outline-secondary').addClass('btn-secondary');
                    
                    table.treegrid({
                        treeColumn: 0,
                        onChange: function() {
                            table.bootstrapTable('resetView');
                        },
                        onExpand: function() {
                            
                        }
                    });
                } else {
                    $('#view-category-tree').removeClass('btn-secondary').addClass('btn-outline-secondary');
                    $('#view-category-list').removeClass('btn-outline-secondary').addClass('btn-secondary');
                }
            }
        },
        columns: [
            {
                checkbox: true,
                title: '{% trans "Select" %}',
                searchable: false,
                switchable: false,
                visible: false,
            },
            {
                field: 'name',
                title: '{% trans "Name" %}',
                switchable: true,
                sortable: true,
                formatter: function(value, row) {

                    var html = renderLink(
                        value,
                        `/part/category/${row.pk}/`
                    );

                    if (row.starred) {
                        html += makeIconBadge('fa-bell icon-green', '{% trans "Subscribed category" %}');
                    }

                    return html;
                }
            },
            {
                field: 'description',
                title: '{% trans "Description" %}',
                switchable: true,
                sortable: false,
            },
            {
                field: 'pathstring',
                title: '{% trans "Path" %}',
                switchable: !tree_view,
                visible: !tree_view,
                sortable: false,
            },
            {
                field: 'parts',
                title: '{% trans "Parts" %}',
                switchable: true,
                sortable: false,
            }
        ]
    });
}

function loadPartTestTemplateTable(table, options) {
    /*
     * Load PartTestTemplate table.
     */

    var params = options.params || {};

    var part = options.part || null;

    var filterListElement = options.filterList || '#filter-list-parttests';

    var filters = loadTableFilters('parttests');

    var original = {};

    for (var k in params) {
        original[k] = params[k];
    }

    setupFilterList('parttests', table, filterListElement);

    // Override the default values, or add new ones
    for (var key in params) {
        filters[key] = params[key];
    }

    table.inventreeTable({
        method: 'get',
        formatNoMatches: function() {
            return '{% trans "No test templates matching query" %}';
        },
        url: '{% url "api-part-test-template-list" %}',
        queryParams: filters,
        name: 'testtemplate',
        original: original,
        columns: [
            {
                field: 'pk',
                title: 'ID',
                visible: false,
            },
            {
                field: 'test_name',
                title: '{% trans "Test Name" %}',
                sortable: true,
            },
            {
                field: 'description',
                title: '{% trans "Description" %}',
            },
            {
                field: 'required',
                title: '{% trans "Required" %}',
                sortable: true,
                formatter: function(value) {
                    return yesNoLabel(value);
                }
            },
            {
                field: 'requires_value',
                title: '{% trans "Requires Value" %}',
                formatter: function(value) {
                    return yesNoLabel(value);
                }
            },
            {
                field: 'requires_attachment',
                title: '{% trans "Requires Attachment" %}',
                formatter: function(value) {
                    return yesNoLabel(value);
                }
            },
            {
                field: 'buttons',
                formatter: function(value, row) {
                    var pk = row.pk;

                    if (row.part == part) {
                        var html = `<div class='btn-group float-right' role='group'>`;

                        html += makeIconButton('fa-edit icon-blue', 'button-test-edit', pk, '{% trans "Edit test result" %}');
                        html += makeIconButton('fa-trash-alt icon-red', 'button-test-delete', pk, '{% trans "Delete test result" %}');

                        html += `</div>`;

                        return html;
                    } else {
                        var text = '{% trans "This test is defined for a parent part" %}';

                        return renderLink(text, `/part/${row.part}/tests/`); 
                    }
                }
            }
        ],
        onPostBody: function() {

            table.find('.button-test-edit').click(function() {
                var pk = $(this).attr('pk');
            
                var url = `/api/part/test-template/${pk}/`;
            
                constructForm(url, {
                    fields: {
                        test_name: {},
                        description: {},
                        required: {},
                        requires_value: {},
                        requires_attachment: {},
                    },
                    title: '{% trans "Edit Test Result Template" %}',
                    onSuccess: function() {
                        table.bootstrapTable('refresh');
                    },
                });
            });

            table.find('.button-test-delete').click(function() {
                var pk = $(this).attr('pk');
            
                var url = `/api/part/test-template/${pk}/`;
            
                constructForm(url, {
                    method: 'DELETE',
                    title: '{% trans "Delete Test Result Template" %}',
                    onSuccess: function() {
                        table.bootstrapTable('refresh');
                    },
                });
            });
        }
    });
}


function loadPriceBreakTable(table, options) {
    /*
     * Load PriceBreak table.
     */

    var name = options.name || 'pricebreak';
    var human_name = options.human_name || 'price break';
    var linkedGraph = options.linkedGraph || null;
    var chart = null;

    table.inventreeTable({
        name: name,
        method: 'get',
        formatNoMatches: function() {
            return `{% trans "No ${human_name} information found" %}`;
        },
        queryParams: {
            part: options.part
        },
        url: options.url,
        onLoadSuccess: function(tableData) {
            if (linkedGraph) {
                // sort array
                tableData = tableData.sort((a, b) => (a.quantity - b.quantity));

                // split up for graph definition
                var graphLabels = Array.from(tableData, (x) => (x.quantity));
                var graphData = Array.from(tableData, (x) => (x.price));

                // destroy chart if exists
                if (chart) {
                    chart.destroy();
                }
                chart = loadLineChart(linkedGraph,
                    {
                        labels: graphLabels,
                        datasets: [
                            {
                                label: '{% trans "Unit Price" %}',
                                data: graphData,
                                backgroundColor: 'rgba(255, 206, 86, 0.2)',
                                borderColor: 'rgb(255, 206, 86)',
                                stepped: true,
                                fill: true,
                            },
                        ],
                    }
                );
            }
        },
        columns: [
            {
                field: 'pk',
                title: 'ID',
                visible: false,
                switchable: false,
            },
            {
                field: 'quantity',
                title: '{% trans "Quantity" %}',
                sortable: true,
            },
            {
                field: 'price',
                title: '{% trans "Price" %}',
                sortable: true,
                formatter: function(value, row) {
                    var html = value;
    
                    html += `<div class='btn-group float-right' role='group'>`;

                    html += makeIconButton('fa-edit icon-blue', `button-${name}-edit`, row.pk, `{% trans "Edit ${human_name}" %}`);
                    html += makeIconButton('fa-trash-alt icon-red', `button-${name}-delete`, row.pk, `{% trans "Delete ${human_name}" %}`);
    
                    html += `</div>`;
    
                    return html;
                }
            },
        ]
    });
}

function loadLineChart(context, data) {
    return new Chart(context, {
        type: 'line',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {position: 'bottom'},
            }
        }
    });
}

function initPriceBreakSet(table, options) {

    var part_id = options.part_id;
    var pb_human_name = options.pb_human_name;
    var pb_url_slug = options.pb_url_slug;
    var pb_url = options.pb_url;
    var pb_new_btn = options.pb_new_btn;
    var pb_new_url = options.pb_new_url;

    var linkedGraph = options.linkedGraph || null;

    loadPriceBreakTable(
        table,
        {
            name: pb_url_slug,
            human_name: pb_human_name,
            url: pb_url,
            linkedGraph: linkedGraph,
            part: part_id,
        }
    );

    function reloadPriceBreakTable() {
        table.bootstrapTable('refresh');
    }

    pb_new_btn.click(function() {

        constructForm(pb_new_url, {
            fields: {
                part: {
                    hidden: true,
                    value: part_id,
                },
                quantity: {},
                price: {},
                price_currency: {},
            },
            method: 'POST',
            title: '{% trans "Add Price Break" %}',
            onSuccess: reloadPriceBreakTable,
        });
    });

    table.on('click', `.button-${pb_url_slug}-delete`, function() {
        var pk = $(this).attr('pk');

        constructForm(`${pb_url}${pk}/`, {
            method: 'DELETE',
            title: '{% trans "Delete Price Break" %}',
            onSuccess: reloadPriceBreakTable,
        });
    });

    table.on('click', `.button-${pb_url_slug}-edit`, function() {
        var pk = $(this).attr('pk');

        constructForm(`${pb_url}${pk}/`, {
            fields: {
                quantity: {},
                price: {},
                price_currency: {},
            },
            title: '{% trans "Edit Price Break" %}',
            onSuccess: reloadPriceBreakTable,
        });
    });
}


function loadPartSchedulingChart(canvas_id, part_id) {

    var part_info = null;

    // First, grab updated data for the particular part
    inventreeGet(`/api/part/${part_id}/`, {}, {
        async: false,
        success: function(response) {
            part_info = response;
        }
    });

    var today = moment();

    // Create an initial entry, using the available quantity
    var stock_schedule = [
        {
            date: today,
            delta: 0,
            label: '{% trans "Current Stock" %}',
        }
    ];

    /* Request scheduling information for the part.
     * Note that this information has already been 'curated' by the server,
     * and arranged in increasing chronological order
     */
    inventreeGet(
        `/api/part/${part_id}/scheduling/`,
        {},
        {
            async: false,
            success: function(response) {
                response.forEach(function(entry) {
                    stock_schedule.push({
                        date: moment(entry.date),
                        delta: entry.quantity,
                        title: entry.title,
                        label: entry.label,
                        url: entry.url,
                    });
                });
            }
        }
    );

    // If no scheduling information is available for the part,
    // remove the chart and display a message instead
    if (stock_schedule.length <= 1) {

        var message = `
        <div class='alert alert-block alert-info'>
            {% trans "No scheduling information available for this part" %}.<br>
        </div>`;

        var canvas_element = $('#part-schedule-chart');

        canvas_element.closest('div').html(message);

        return;
    }

    // Iterate through future "events" to calculate expected quantity

    var quantity = part_info.in_stock;

    for (var idx = 0; idx < stock_schedule.length; idx++) {

        quantity += stock_schedule[idx].delta;

        stock_schedule[idx].x = stock_schedule[idx].date.format('YYYY-MM-DD');
        stock_schedule[idx].y = quantity;
    }

    var context = document.getElementById(canvas_id);

    const data = {
        datasets: [{
            label: '{% trans "Scheduled Stock Quantities" %}',
            data: stock_schedule,
            backgroundColor: 'rgb(220, 160, 80)',
            borderWidth: 2,
            borderColor: 'rgb(90, 130, 150)'
        }],
    };

    return new Chart(context, {
        type: 'scatter',
        data: data,
        options: {
            showLine: true,
            stepped: true,
            scales: {
                x: {
                    type: 'time',
                    min: today.format(),
                    position: 'bottom',
                    time: {
                        unit: 'day',
                    },
                },
                y: {
                    beginAtZero: true,
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(item) {
                            return item.raw.label;
                        },
                        beforeLabel: function(item) {
                            return item.raw.title;
                        },
                        afterLabel: function(item) {
                            var delta = item.raw.delta;

                            if (delta == 0) {
                                delta = '';
                            } else {
                                delta = ` (${item.raw.delta > 0 ? '+' : ''}${item.raw.delta})`;
                            }

                            return `{% trans "Quantity" %}: ${item.raw.y}${delta}`;
                        }
                    }
                }
            },
        }
    });
}


function loadStockPricingChart(context, data) {
    return new Chart(context, {
        type: 'bar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {legend: {position: 'bottom'}},
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    grid: {display: false},
                    title: {
                        display: true,
                        text: '{% trans "Single Price" %}'
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    grid: {display: false},
                    titel: {
                        display: true,
                        text: '{% trans "Quantity" %}',
                        position: 'right'
                    }
                },
                y2: {
                    type: 'linear',
                    position: 'left',
                    grid: {display: false},
                    title: {
                        display: true,
                        text: '{% trans "Single Price Difference" %}'
                    }
                }
            },
        }
    });
}


function loadBomChart(context, data) {
    return new Chart(context, {
        type: 'doughnut',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                },
                scales: {
                    xAxes: [
                        {
                            beginAtZero: true,
                            ticks: {
                                autoSkip: false,
                            }
                        }
                    ]
                }
            }
        }
    });
}


function loadSellPricingChart(context, data) {
    return new Chart(context, {
        type: 'line',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    grid: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: '{% trans "Unit Price" %}',
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    grid: {
                        display: false
                    },
                    titel: {
                        display: true,
                        text: '{% trans "Quantity" %}',
                        position: 'right'
                    }
                },
            },
        }
    });
}
