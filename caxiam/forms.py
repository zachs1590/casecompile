from django import forms
from django.core.exceptions import ValidationError
from django.template import Context
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.translation import ugettext_lazy as _

from caxiam.common import Enumeration
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, TEMPLATE_PACK
from crispy_forms.utils import render_field

class CrispyMixin(object):

    def __init__(self, *args, **kwargs):
        super(CrispyMixin, self).__init__(*args,**kwargs)
        self.helper = FormHelper(self)
        self.helper.form_id = self.__class__.__name__
        self.setup_form_helper(helper = self.helper)

    def setup_form_helper(self, helper):
        pass

# Crispy Forms Layouts don't have a list object to use in the layouts.
class Ul(Div):
    # All the other layout objects live in uni_form/layout so i have mine overriding into that folder too.
    template = "uni_form/layout/ul.html"

    # The original Div render turned all the fields into one string and then they would output them,
    # but that wouldn't allow me to do a li around each field in the set.  so I am passing out a list of fields
    def render(self, form, form_style, context, template_pack=TEMPLATE_PACK):
        fields = []
        for field in self.fields:
            fields.append(render_field(field, form, form_style, context, template_pack=template_pack))
        return render_to_string(self.template, Context({'ul': self, 'fields': fields}))

# a class that validates a comma-separated list
# of numbers
class IntegerListField(forms.Field):
    widget = forms.HiddenInput      # by default
    default_error_messages = {
        'invalid': _('invalid'),    # this is actually defined in the form error messages
    }

    # cast the input data to native Python values
    def to_python(self, value):
        if value in self.empty_values:
            return None
            
        separated_values = value.split()
        parsed_values = []
        invalid_values = []
        for v in separated_values:
            try:
                parsed_values.append(int(v))
            except (ValueError, TypeError):
                invalid_values.append(v)

        # if we have any invalid values, raise ONE exception
        # with ALL of them listed
        if len(invalid_values):
            safe_invalid_entries = ','.join([ escape(v) for v in invalid_values ])
            raise ValidationError(self.error_messages['invalid'], code='invalid', params={'invalid_entries':safe_invalid_entries})

        # all good, give back the list
        return parsed_values

# This list is problematic, as it excludes many state-like
# entries that are valid "US" addresses (Puerto Rico, District
# of Columbia, etc.)
#
US_STATES = Enumeration(
        ("AL", 'ALABAMA', "Alabama"),
        ("AK", 'ALASKA', "Alaska"),
        ("AZ", 'ARIZONA', "Arizona"),
        ("AR", 'ARKANSAS', "Arkansas"),
        ("CA", 'CALIFORNIA', "California"),
        ("CO", 'COLORADO', "Colorado"),
        ("CT", 'CONNECTICUT', "Connecticut"),
        ("DC", 'DISTRICT_OF_COLUMBIA', "D.C."), # because nobody writes "District of Columbia", ever
        ("DE", 'DELAWARE', "Delaware"),
        ("FL", 'FLORIDA', "Florida"),
        ("GA", 'GEORGIA', "Georgia"),
        ("HI", 'HAWAII', "Hawaii"),
        ("ID", 'IDAHO', "Idaho"),
        ("IL", 'ILLINOIS', "Illinois"),
        ("IN", 'INDIANA', "Indiana"),
        ("IA", 'IOWA', "Iowa"),
        ("KS", 'KANSAS', "Kansas"),
        ("KY", 'KENTUCKY', "Kentucky"),
        ("LA", 'LOUISIANA', "Louisiana"),
        ("ME", 'MAINE', "Maine"),
        ("MD", 'MARYLAND', "Maryland"),
        ("MA", 'MASSACHUSETTS', "Massachusetts"),
        ("MI", 'MICHIGAN', "Michigan"),
        ("MN", 'MINNESOTA', "Minnesota"),
        ("MS", 'MISSISSIPPI', "Mississippi"),
        ("MO", 'MISSOURI', "Missouri"),
        ("MT", 'MONTANA', "Montana"),
        ("NE", 'NEBRASKA', "Nebraska"),
        ("NV", 'NEVADA', "Nevada"),
        ("NH", 'NEW_HAMPSHIRE', "New Hampshire"),
        ("NJ", 'NEW_JERSEY', "New Jersey"),
        ("NM", 'NEW_MEXICO', "New Mexico"),
        ("NY", 'NEW_YORK', "New York"),
        ("NC", 'NORTH_CAROLINA', "North Carolina"),
        ("ND", 'NORTH_DAKOTA', "North Dakota"),
        ("OH", 'OHIO', "Ohio"),
        ("OK", 'OKLAHOMA', "Oklahoma"),
        ("OR", 'OREGON', "Oregon"),
        ("PA", 'PENNSYLVANIA', "Pennsylvania"),
        ("RI", 'RHODE_ISLAND', "Rhode Island"),
        ("SC", 'SOUTH_CAROLINA', "South Carolina"),
        ("SD", 'SOUTH_DAKOTA', "South Dakota"),
        ("TN", 'TENNESSEE', "Tennessee"),
        ("TX", 'TEXAS', "Texas"),
        ("UT", 'UTAH', "Utah"),
        ("VT", 'VERMONT', "Vermont"),
        ("VA", 'VIRGINIA', "Virginia"),
        ("WA", 'WASHINGTON', "Washington"),
        ("WV", 'WEST_VIRGINIA', "West Virginia"),
        ("WI", 'WISCONSIN', "Wisconsin"),
        ("WY", 'WYOMING', "Wyoming"),  
    )
    
# ISO 3166-1-alpha-2; see http://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
# NOTE: this uses a string value as the enumeration value
# rather than an integer; for this we actually treat the
# value and the label as the same, with additional columns
# for the display value and the country TLD
ISO_COUNTRIES = Enumeration(
        ( 'AF', 'AF', 'Afghanistan', '.af' ),
        ( 'AX', 'AX', '&Aring;land Islands', '.ax' ),
        ( 'AL', 'AL', 'Albania', '.al' ),
        ( 'DZ', 'DZ', 'Algeria', '.dz' ),
        ( 'AS', 'AS', 'American Samoa', '.as' ),
        ( 'AD', 'AD', 'Andorra', '.ad' ),
        ( 'AO', 'AO', 'Angola', '.ao' ),
        ( 'AI', 'AI', 'Anguilla', '.ai' ),
        ( 'AQ', 'AQ', 'Antarctica', '.aq' ),
        ( 'AG', 'AG', 'Antigua and Barbuda', '.ag' ),
        ( 'AR', 'AR', 'Argentina', '.ar' ),
        ( 'AM', 'AM', 'Armenia', '.am' ),
        ( 'AW', 'AW', 'Aruba', '.aw' ),
        ( 'AU', 'AU', 'Australia', '.au' ),
        ( 'AT', 'AT', 'Austria', '.at' ),
        ( 'AZ', 'AZ', 'Azerbaijan', '.az' ),
        ( 'BS', 'BS', 'Bahamas', '.bs' ),
        ( 'BH', 'BH', 'Bahrain', '.bh' ),
        ( 'BD', 'BD', 'Bangladesh', '.bd' ),
        ( 'BB', 'BB', 'Barbados', '.bb' ),
        ( 'BY', 'BY', 'Belarus', '.by' ),
        ( 'BE', 'BE', 'Belgium', '.be' ),
        ( 'BZ', 'BZ', 'Belize', '.bz' ),
        ( 'BJ', 'BJ', 'Benin', '.bj' ),
        ( 'BM', 'BM', 'Bermuda', '.bm' ),
        ( 'BT', 'BT', 'Bhutan', '.bt' ),
        ( 'BO', 'BO', 'Bolivia, Plurinational State of', '.bo' ),
        ( 'BQ', 'BQ', 'Bonaire, Sint Eustatius and Saba', '.bq' ),
        ( 'BA', 'BA', 'Bosnia and Herzegovina', '.ba' ),
        ( 'BW', 'BW', 'Botswana', '.bw' ),
        ( 'BV', 'BV', 'Bouvet Island', '.bv' ),
        ( 'BR', 'BR', 'Brazil', '.br' ),
        ( 'IO', 'IO', 'British Indian Ocean Territory', '.io' ),
        ( 'BN', 'BN', 'Brunei Darussalam', '.bn' ),
        ( 'BG', 'BG', 'Bulgaria', '.bg' ),
        ( 'BF', 'BF', 'Burkina Faso', '.bf' ),
        ( 'BI', 'BI', 'Burundi', '.bi' ),
        ( 'CV', 'CV', 'Cabo Verde', '.cv' ),
        ( 'KH', 'KH', 'Cambodia', '.kh' ),
        ( 'CM', 'CM', 'Cameroon', '.cm' ),
        ( 'CA', 'CA', 'Canada', '.ca' ),
        ( 'KY', 'KY', 'Cayman Islands', '.ky' ),
        ( 'CF', 'CF', 'Central African Republic', '.cf' ),
        ( 'TD', 'TD', 'Chad', '.td' ),
        ( 'CL', 'CL', 'Chile', '.cl' ),
        ( 'CN', 'CN', 'China', '.cn' ),
        ( 'CX', 'CX', 'Christmas Island', '.cx' ),
        ( 'CC', 'CC', 'Cocos (Keeling) Islands', '.cc' ),
        ( 'CO', 'CO', 'Colombia', '.co' ),
        ( 'KM', 'KM', 'Comoros', '.km' ),
        ( 'CG', 'CG', 'Congo', '.cg' ),
        ( 'CD', 'CD', 'Congo, the Democratic Republic of the', '.cd' ),
        ( 'CK', 'CK', 'Cook Islands', '.ck' ),
        ( 'CR', 'CR', 'Costa Rica', '.cr' ),
        ( 'HR', 'HR', 'Croatia', '.hr' ),
        ( 'CU', 'CU', 'Cuba', '.cu' ),
        ( 'CW', 'CW', 'Cura&ccedil;ao', '.cw' ),
        ( 'CY', 'CY', 'Cyprus', '.cy' ),
        ( 'CZ', 'CZ', 'Czech Republic', '.cz' ),
        ( 'CI', 'CI', 'C&ocirc;te d&#8217;Ivoire', '.ci' ),
        ( 'DK', 'DK', 'Denmark', '.dk' ),
        ( 'DJ', 'DJ', 'Djibouti', '.dj' ),
        ( 'DM', 'DM', 'Dominica', '.dm' ),
        ( 'DO', 'DO', 'Dominican Republic', '.do' ),
        ( 'EC', 'EC', 'Ecuador', '.ec' ),
        ( 'EG', 'EG', 'Egypt', '.eg' ),
        ( 'SV', 'SV', 'El Salvador', '.sv' ),
        ( 'GQ', 'GQ', 'Equatorial Guinea', '.gq' ),
        ( 'ER', 'ER', 'Eritrea', '.er' ),
        ( 'EE', 'EE', 'Estonia', '.ee' ),
        ( 'ET', 'ET', 'Ethiopia', '.et' ),
        ( 'FK', 'FK', 'Falkland Islands (Malvinas)', '.fk' ),
        ( 'FO', 'FO', 'Faroe Islands', '.fo' ),
        ( 'FJ', 'FJ', 'Fiji', '.fj' ),
        ( 'FI', 'FI', 'Finland', '.fi' ),
        ( 'FR', 'FR', 'France', '.fr' ),
        ( 'PF', 'PF', 'French Polynesia', '.pf' ),
        ( 'GF', 'GF', 'French Guiana', '.gf' ),
        ( 'TF', 'TF', 'French Southern Territories', '.tf' ),
        ( 'GA', 'GA', 'Gabon', '.ga' ),
        ( 'GM', 'GM', 'Gambia', '.gm' ),
        ( 'GE', 'GE', 'Georgia', '.ge' ),
        ( 'DE', 'DE', 'Germany', '.de' ),
        ( 'GH', 'GH', 'Ghana', '.gh' ),
        ( 'GI', 'GI', 'Gibraltar', '.gi' ),
        ( 'GR', 'GR', 'Greece', '.gr' ),
        ( 'GL', 'GL', 'Greenland', '.gl' ),
        ( 'GD', 'GD', 'Grenada', '.gd' ),
        ( 'GP', 'GP', 'Guadeloupe', '.gp' ),
        ( 'GU', 'GU', 'Guam', '.gu' ),
        ( 'GT', 'GT', 'Guatemala', '.gt' ),
        ( 'GG', 'GG', 'Guernsey', '.gg' ),
        ( 'GN', 'GN', 'Guinea', '.gn' ),
        ( 'GW', 'GW', 'Guinea-Bissau', '.gw' ),
        ( 'GY', 'GY', 'Guyana', '.gy' ),
        ( 'HT', 'HT', 'Haiti', '.ht' ),
        ( 'HM', 'HM', 'Heard Island and McDonald Islands', '.hm' ),
        ( 'VA', 'VA', 'Holy See (Vatican City State)', '.va' ),
        ( 'HN', 'HN', 'Honduras', '.hn' ),
        ( 'HK', 'HK', 'Hong Kong', '.hk' ),
        ( 'HU', 'HU', 'Hungary', '.hu' ),
        ( 'IS', 'IS', 'Iceland', '.is' ),
        ( 'IN', 'IN', 'India', '.in' ),
        ( 'ID', 'ID', 'Indonesia', '.id' ),
        ( 'IR', 'IR', 'Iran, Islamic Republic of', '.ir' ),
        ( 'IQ', 'IQ', 'Iraq', '.iq' ),
        ( 'IE', 'IE', 'Ireland', '.ie' ),
        ( 'IM', 'IM', 'Isle of Man', '.im' ),
        ( 'IL', 'IL', 'Israel', '.il' ),
        ( 'IT', 'IT', 'Italy', '.it' ),
        ( 'JM', 'JM', 'Jamaica', '.jm' ),
        ( 'JP', 'JP', 'Japan', '.jp' ),
        ( 'JE', 'JE', 'Jersey', '.je' ),
        ( 'JO', 'JO', 'Jordan', '.jo' ),
        ( 'KZ', 'KZ', 'Kazakhstan', '.kz' ),
        ( 'KE', 'KE', 'Kenya', '.ke' ),
        ( 'KI', 'KI', 'Kiribati', '.ki' ),
        ( 'KR', 'KR', 'Korea, Republic of', '.kr' ),
        ( 'KP', 'KP', 'Korea, Democratic People&#8217;s Republic of', '.kp' ),
        ( 'KW', 'KW', 'Kuwait', '.kw' ),
        ( 'KG', 'KG', 'Kyrgyzstan', '.kg' ),
        ( 'LA', 'LA', 'Lao People&#8217;s Democratic Republic', '.la' ),
        ( 'LV', 'LV', 'Latvia', '.lv' ),
        ( 'LB', 'LB', 'Lebanon', '.lb' ),
        ( 'LS', 'LS', 'Lesotho', '.ls' ),
        ( 'LR', 'LR', 'Liberia', '.lr' ),
        ( 'LY', 'LY', 'Libya', '.ly' ),
        ( 'LI', 'LI', 'Liechtenstein', '.li' ),
        ( 'LT', 'LT', 'Lithuania', '.lt' ),
        ( 'LU', 'LU', 'Luxembourg', '.lu' ),
        ( 'MO', 'MO', 'Macao', '.mo' ),
        ( 'MK', 'MK', 'Macedonia, the former Yugoslav Republic of', '.mk' ),
        ( 'MG', 'MG', 'Madagascar', '.mg' ),
        ( 'MW', 'MW', 'Malawi', '.mw' ),
        ( 'MY', 'MY', 'Malaysia', '.my' ),
        ( 'MV', 'MV', 'Maldives', '.mv' ),
        ( 'ML', 'ML', 'Mali', '.ml' ),
        ( 'MT', 'MT', 'Malta', '.mt' ),
        ( 'MH', 'MH', 'Marshall Islands', '.mh' ),
        ( 'MQ', 'MQ', 'Martinique', '.mq' ),
        ( 'MR', 'MR', 'Mauritania', '.mr' ),
        ( 'MU', 'MU', 'Mauritius', '.mu' ),
        ( 'YT', 'YT', 'Mayotte', '.yt' ),
        ( 'MX', 'MX', 'Mexico', '.mx' ),
        ( 'FM', 'FM', 'Micronesia, Federated States of', '.fm' ),
        ( 'MD', 'MD', 'Moldova, Republic of', '.md' ),
        ( 'MC', 'MC', 'Monaco', '.mc' ),
        ( 'MN', 'MN', 'Mongolia', '.mn' ),
        ( 'ME', 'ME', 'Montenegro', '.me' ),
        ( 'MS', 'MS', 'Montserrat', '.ms' ),
        ( 'MA', 'MA', 'Morocco', '.ma' ),
        ( 'MZ', 'MZ', 'Mozambique', '.mz' ),
        ( 'MM', 'MM', 'Myanmar', '.mm' ),
        ( 'NA', 'NA', 'Namibia', '.na' ),
        ( 'NR', 'NR', 'Nauru', '.nr' ),
        ( 'NP', 'NP', 'Nepal', '.np' ),
        ( 'NL', 'NL', 'Netherlands', '.nl' ),
        ( 'NC', 'NC', 'New Caledonia', '.nc' ),
        ( 'NZ', 'NZ', 'New Zealand', '.nz' ),
        ( 'NI', 'NI', 'Nicaragua', '.ni' ),
        ( 'NE', 'NE', 'Niger', '.ne' ),
        ( 'NG', 'NG', 'Nigeria', '.ng' ),
        ( 'NU', 'NU', 'Niue', '.nu' ),
        ( 'NF', 'NF', 'Norfolk Island', '.nf' ),
        ( 'MP', 'MP', 'Northern Mariana Islands', '.mp' ),
        ( 'NO', 'NO', 'Norway', '.no' ),
        ( 'OM', 'OM', 'Oman', '.om' ),
        ( 'PK', 'PK', 'Pakistan', '.pk' ),
        ( 'PW', 'PW', 'Palau', '.pw' ),
        ( 'PS', 'PS', 'Palestine, State of', '.ps' ),
        ( 'PA', 'PA', 'Panama', '.pa' ),
        ( 'PG', 'PG', 'Papua New Guinea', '.pg' ),
        ( 'PY', 'PY', 'Paraguay', '.py' ),
        ( 'PE', 'PE', 'Peru', '.pe' ),
        ( 'PH', 'PH', 'Philippines', '.ph' ),
        ( 'PN', 'PN', 'Pitcairn', '.pn' ),
        ( 'PL', 'PL', 'Poland', '.pl' ),
        ( 'PT', 'PT', 'Portugal', '.pt' ),
        ( 'PR', 'PR', 'Puerto Rico', '.pr' ),
        ( 'QA', 'QA', 'Qatar', '.qa' ),
        ( 'RO', 'RO', 'Romania', '.ro' ),
        ( 'RU', 'RU', 'Russian Federation', '.ru' ),
        ( 'RW', 'RW', 'Rwanda', '.rw' ),
        ( 'RE', 'RE', 'R&eacute;union', '.re' ),
        ( 'BL', 'BL', 'Saint Barth&eacute;lemy', '.bl' ),
        ( 'SH', 'SH', 'Saint Helena, Ascension and Tristan da Cunha', '.sh' ),
        ( 'KN', 'KN', 'Saint Kitts and Nevis', '.kn' ),
        ( 'LC', 'LC', 'Saint Lucia', '.lc' ),
        ( 'MF', 'MF', 'Saint Martin (French part)', '.mf' ),
        ( 'PM', 'PM', 'Saint Pierre and Miquelon', '.pm' ),
        ( 'VC', 'VC', 'Saint Vincent and the Grenadines', '.vc' ),
        ( 'WS', 'WS', 'Samoa', '.ws' ),
        ( 'SM', 'SM', 'San Marino', '.sm' ),
        ( 'ST', 'ST', 'Sao Tome and Principe', '.st' ),
        ( 'SA', 'SA', 'Saudi Arabia', '.sa' ),
        ( 'SN', 'SN', 'Senegal', '.sn' ),
        ( 'RS', 'RS', 'Serbia', '.rs' ),
        ( 'SC', 'SC', 'Seychelles', '.sc' ),
        ( 'SL', 'SL', 'Sierra Leone', '.sl' ),
        ( 'SG', 'SG', 'Singapore', '.sg' ),
        ( 'SX', 'SX', 'Sint Maarten (Dutch part)', '.sx' ),
        ( 'SK', 'SK', 'Slovakia', '.sk' ),
        ( 'SI', 'SI', 'Slovenia', '.si' ),
        ( 'SB', 'SB', 'Solomon Islands', '.sb' ),
        ( 'SO', 'SO', 'Somalia', '.so' ),
        ( 'ZA', 'ZA', 'South Africa', '.za' ),
        ( 'GS', 'GS', 'South Georgia and the South Sandwich Islands', '.gs' ),
        ( 'SS', 'SS', 'South Sudan', '.ss' ),
        ( 'ES', 'ES', 'Spain', '.es' ),
        ( 'LK', 'LK', 'Sri Lanka', '.lk' ),
        ( 'SD', 'SD', 'Sudan', '.sd' ),
        ( 'SR', 'SR', 'Suriname', '.sr' ),
        ( 'SJ', 'SJ', 'Svalbard and Jan Mayen', '.sj' ),
        ( 'SZ', 'SZ', 'Swaziland', '.sz' ),
        ( 'SE', 'SE', 'Sweden', '.se' ),
        ( 'CH', 'CH', 'Switzerland', '.ch' ),
        ( 'SY', 'SY', 'Syrian Arab Republic', '.sy' ),
        ( 'TW', 'TW', 'Taiwan, Province of China', '.tw' ),
        ( 'TJ', 'TJ', 'Tajikistan', '.tj' ),
        ( 'TZ', 'TZ', 'Tanzania, United Republic of', '.tz' ),
        ( 'TH', 'TH', 'Thailand', '.th' ),
        ( 'TL', 'TL', 'Timor-Leste', '.tl' ),
        ( 'TG', 'TG', 'Togo', '.tg' ),
        ( 'TK', 'TK', 'Tokelau', '.tk' ),
        ( 'TO', 'TO', 'Tonga', '.to' ),
        ( 'TT', 'TT', 'Trinidad and Tobago', '.tt' ),
        ( 'TN', 'TN', 'Tunisia', '.tn' ),
        ( 'TR', 'TR', 'Turkey', '.tr' ),
        ( 'TM', 'TM', 'Turkmenistan', '.tm' ),
        ( 'TC', 'TC', 'Turks and Caicos Islands', '.tc' ),
        ( 'TV', 'TV', 'Tuvalu', '.tv' ),
        ( 'UG', 'UG', 'Uganda', '.ug' ),
        ( 'UA', 'UA', 'Ukraine', '.ua' ),
        ( 'GB', 'GB', 'United Kingdom', '.uk' ),
        ( 'UM', 'UM', 'United States Minor Outlying Islands', '.um' ),
        ( 'AE', 'AE', 'United Arab Emirates', '.ae' ),
        ( 'US', 'US', 'United States', '.us' ),
        ( 'UY', 'UY', 'Uruguay', '.uy' ),
        ( 'UZ', 'UZ', 'Uzbekistan', '.uz' ),
        ( 'VU', 'VU', 'Vanuatu', '.vu' ),
        ( 'VE', 'VE', 'Venezuela, Bolivarian Republic of', '.ve' ),
        ( 'VN', 'VN', 'Viet Nam', '.vn' ),
        ( 'VG', 'VG', 'Virgin Islands, British', '.vg' ),
        ( 'VI', 'VI', 'Virgin Islands, U.S.', '.vi' ),
        ( 'WF', 'WF', 'Wallis and Futuna', '.wf' ),
        ( 'EH', 'EH', 'Western Sahara', '.eh' ),
        ( 'YE', 'YE', 'Yemen', '.ye' ),
        ( 'ZM', 'ZM', 'Zambia', '.zm' ),
        ( 'ZW', 'ZW', 'Zimbabwe', '.zw' ),
    )
