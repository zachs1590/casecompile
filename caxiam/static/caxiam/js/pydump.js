$(document).on(
	{
		'click': function (e) {
			e.preventDefault();
			e.stopPropagation();

			var t = $(this);
			if (t.hasClass('cx_dbg_disabled'))
			{
				t.removeClass('cx_dbg_disabled');
				t.next().show();
			}
			else
			{
				t.addClass('cx_dbg_disabled');
				t.next().hide();
			}
		}
	},
	'.cx_dbg td:not(.cx_dbg_title)'
);
