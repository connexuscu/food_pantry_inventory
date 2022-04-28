{% load inventree_extras %}

/* exported
    editSetting,
    user_settings,
    global_settings,
    plugins_enabled,
*/

{% user_settings request.user as USER_SETTINGS %}
const user_settings = {
    {% for key, value in USER_SETTINGS.items %}
    {{ key }}: {% primitive_to_javascript value %},
    {% endfor %}
};

{% visible_global_settings as GLOBAL_SETTINGS %}
const global_settings = {
    {% for key, value in GLOBAL_SETTINGS.items %}
    {{ key }}: {% primitive_to_javascript value %},
    {% endfor %}
};

{% plugins_enabled as p_en %}
{% if p_en %}
const plugins_enabled = true;
{% else %}
const plugins_enabled = false;
{% endif %}

/*
 * Edit a setting value
 */
function editSetting(pk, options={}) {

    // Is this a global setting or a user setting?
    var global = options.global || false;

    var plugin = options.plugin;

    var url = '';

    if (plugin) {
        url = `/api/plugin/settings/${pk}/`;
    } else if (global) {
        url = `/api/settings/global/${pk}/`;
    } else {
        url = `/api/settings/user/${pk}/`;
    }

    var reload_required = false;

    // First, read the settings object from the server
    inventreeGet(url, {}, {
        success: function(response) {
    
            if (response.choices && response.choices.length > 0) {
                response.type = 'choice';
                reload_required = true;
            }

            // Construct the field 
            var fields = {
                value: {
                    label: response.name,
                    help_text: response.description,
                    type: response.type,
                    choices: response.choices,
                }
            };

            constructChangeForm(fields, {
                url: url,
                method: 'PATCH',
                title: options.title,
                processResults: function(data, fields, opts) {

                    switch (data.type) {
                    case 'boolean':
                        // Convert to boolean value
                        data.value = data.value.toString().toLowerCase() == 'true';
                        break;
                    case 'integer':
                        // Convert to integer value
                        data.value = parseInt(data.value.toString());
                        break;
                    default:
                        break;
                    }

                    return data;
                },
                processBeforeUpload: function(data) {
                    // Convert value to string
                    data.value = data.value.toString();

                    return data;
                },
                onSuccess: function(response) {

                    var setting = response.key;

                    if (reload_required) {
                        location.reload();
                    } else if (response.type == 'boolean') {
                        var enabled = response.value.toString().toLowerCase() == 'true';
                        $(`#setting-value-${setting}`).prop('checked', enabled);
                    } else {
                        $(`#setting-value-${setting}`).html(response.value);
                    }
                }
            });
        },
        error: function(xhr) {
            showApiError(xhr, url);
        }
    });
}
