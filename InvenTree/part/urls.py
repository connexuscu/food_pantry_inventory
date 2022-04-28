"""
URL lookup for Part app. Provides URL endpoints for:

- Display / Create / Edit / Delete PartCategory
- Display / Create / Edit / Delete Part
- Create / Edit / Delete PartAttachment
- Display / Create / Edit / Delete SupplierPart

"""

from django.conf.urls import url, include

from . import views


part_parameter_urls = [
    url(r'^template/new/', views.PartParameterTemplateCreate.as_view(), name='part-param-template-create'),
    url(r'^template/(?P<pk>\d+)/edit/', views.PartParameterTemplateEdit.as_view(), name='part-param-template-edit'),
    url(r'^template/(?P<pk>\d+)/delete/', views.PartParameterTemplateDelete.as_view(), name='part-param-template-edit'),
]

part_detail_urls = [
    url(r'^delete/?', views.PartDelete.as_view(), name='part-delete'),
    url(r'^bom-download/?', views.BomDownload.as_view(), name='bom-download'),

    url(r'^pricing/', views.PartPricing.as_view(), name='part-pricing'),

    url(r'^bom-upload/?', views.BomUpload.as_view(), name='upload-bom'),

    url(r'^qr_code/?', views.PartQRCode.as_view(), name='part-qr'),

    # Normal thumbnail with form
    url(r'^thumb-select/?', views.PartImageSelect.as_view(), name='part-image-select'),
    url(r'^thumb-download/', views.PartImageDownloadFromURL.as_view(), name='part-image-download'),

    # Any other URLs go to the part detail page
    url(r'^.*$', views.PartDetail.as_view(), name='part-detail'),
]

category_parameter_urls = [
    url(r'^new/', views.CategoryParameterTemplateCreate.as_view(), name='category-param-template-create'),
    url(r'^(?P<pid>\d+)/edit/', views.CategoryParameterTemplateEdit.as_view(), name='category-param-template-edit'),
    url(r'^(?P<pid>\d+)/delete/', views.CategoryParameterTemplateDelete.as_view(), name='category-param-template-delete'),
]

category_urls = [

    # Top level subcategory display
    url(r'^subcategory/', views.PartIndex.as_view(template_name='part/subcategory.html'), name='category-index-subcategory'),

    # Category detail views
    url(r'(?P<pk>\d+)/', include([
        url(r'^delete/', views.CategoryDelete.as_view(), name='category-delete'),
        url(r'^parameters/', include(category_parameter_urls)),

        # Anything else
        url(r'^.*$', views.CategoryDetail.as_view(), name='category-detail'),
    ]))
]

# URL list for part web interface
part_urls = [

    # Upload a part
    url(r'^import/', views.PartImport.as_view(), name='part-import'),
    url(r'^import-api/', views.PartImportAjax.as_view(), name='api-part-import'),

    # Download a BOM upload template
    url(r'^bom_template/?', views.BomUploadTemplate.as_view(), name='bom-upload-template'),

    # Individual part using pk
    url(r'^(?P<pk>\d+)/', include(part_detail_urls)),

    # Part category
    url(r'^category/', include(category_urls)),

    # Part parameters
    url(r'^parameter/', include(part_parameter_urls)),

    # Change category for multiple parts
    url(r'^set-category/?', views.PartSetCategory.as_view(), name='part-set-category'),

    # Individual part using IPN as slug
    url(r'^(?P<slug>[-\w]+)/', views.PartDetailFromIPN.as_view(), name='part-detail-from-ipn'),

    # Top level part list (display top level parts and categories)
    url(r'^.*$', views.PartIndex.as_view(), name='part-index'),
]
