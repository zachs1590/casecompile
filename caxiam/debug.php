<?php
//
// Zirconium Debug Class
//

// This class holds the debugging tools.

class Zirconium_Debug
{
	//
	// data members
	//

	public $writtencss = false;		// support CSS has not been written
	public $writtenscript = false;	// support JavaScript has not been written

	public $Zi = null;
	public $_stack = array( );

	// constructor
	public function __construct($Zi)
	{
		$this->Zi = $Zi;
	}

	// destructor
	function __destruct()
	{
	}

	//
	// member functions
	//

	// cleanup function
	// dumps debug information after page is rendered
	public function cleanup()
	{
		// stop if debug is disabled
		if ($this->Zi->config['debug']['enabled'] == 0)
			return;

		$dbgoutput = array( );
		$this->_setupdebugdump($dbgoutput);

?><span style="position: relative;"><?php
		$this->dump($dbgoutput, $this->Zi->config['debug']['enabled'] == 1);
?></span><?php
	}

	// prep output for display
	// primarily used during cleanup, but may also be invoked during error reporting
	public function _setupdebugdump(&$dbgoutput)
	{
		// list of globals not to show
		// these are the deprecated old-style long names
		$noshow = array_flip(explode(',', 'HTTP_POST_VARS,HTTP_GET_VARS,HTTP_COOKIE_VARS,HTTP_SERVER_VARS,HTTP_ENV_VARS,HTTP_POST_FILES,HTTP_SESSION_VARS,GLOBALS'));

		// seed array of variables to show
		if ($this->Zi->config['debug']['short'])
		{
			$dbgoutput = array(
				'>>' => array(
					'$_SESSION' => &$_SESSION,
					'$_COOKIE' => &$_COOKIE,
					'$_GET' => &$_GET,
					'$_POST' => &$_POST,
					'$_REQUEST' => &$_REQUEST,
					'$_SERVER' => &$_SERVER,
					'$_FILES' => &$_FILES,
					'$Zi->queries' => &$this->Zi->queries,
					),
				);
		}
		else
		{
			$dbgoutput = array(
				'>>' => array(
					'$_SESSION' => &$_SESSION,
					'$_COOKIE' => &$_COOKIE,
					'$_GET' => &$_GET,
					'$_POST' => &$_POST,
					'$_REQUEST' => &$_REQUEST,
					'$_SERVER' => &$_SERVER,
					'$_ENV' => &$_ENV,
					'$_FILES' => &$_FILES,
					'globals' => array( ),
					),
				);
		}

		// fill in globals list with every global not already shown and not on noshow list
		if ($this->Zi->config['debug']['short'] <= 0)
			foreach ($GLOBALS as $key => $value)
				if (!isset($dbgoutput['>>']['$' . $key]) &&
					!isset($noshow[$key]) &&
					!is_null($GLOBALS[$key]))
				{
					$dbgoutput['>>']['globals']['$' . $key] = &$GLOBALS[$key];
				}
	}

	// write support CSS
	public function writecss($wrap = true)
	{
		$this->writtencss = true;

		if ($wrap)
		{
?>
<style type="text/css">
<?php
		}
?>
/* scalars */
.zidbgint {	color: #000080;	background-color: #ffffff;	}
.zidbgdbl {	color: #000080;	background-color: #ffffff;	}
.zidbgstr {	color: #000000;	background-color: #ffffff;	}
.zidbgbool {	color: #008000;	background-color: #ffffff;	}
/* special */
.zidbgnull {	color: #666666;	background-color: #ffffff;	}
.zidbgempty {	color: #666666;	background-color: #ffffff;	}
.zidbgunk {	color: #000000;	background-color: #ffff00;	}
.zidbgrsc {	color: #008080; background-color: #ffffff;	}
.zidbgobj {	color: #cc0000; background-color: #ffffff;	}
/* PHP serialized data */
.zidbgser {	border-collapse: collapse;	border: 2px solid #000000;	}
.zidbgserins { padding: 1px; border: 1px solid #000000; }
.zidbgserkey {
	color: #000000;
	background-color: #cccccc;
	border: 1px solid #000000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgserkeydis {
	color: #555555;
	background-color: #dddddd;
	border: 1px solid #000000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
/* JSON serialized data */
.zidbgjson {	border-collapse: collapse;	border: 2px dotted #000000;	}
.zidbgjsonins { padding: 1px; border: 1px solid #000000; }
.zidbgjsonkey {
	color: #000000;
	background-color: #cccccc;
	border: 1px solid #000000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgjsonkeydis {
	color: #555555;
	background-color: #dddddd;
	border: 1px solid #000000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
/* recordsets & 2D arrays */
.zidbgqry {	border-collapse: collapse;	border: 2px solid #ff0000;	}
.zidbgqrykey, .zidbgqrycol {
	color: #000000;
	background-color: #ffcccc;
	border: 1px solid #ff0000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgqrykeydis, .zidbgqrycoldis {
	color: #555555;
	background-color: #ddcccc;
	border: 1px solid #ff0000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgqrycoldis {
	width: 8px !important;
	}
.zidbgqrycoldis span {
	display: none;
	}
.zidbgqryval, .zidbgqryvaldis {
	color: #000000;
	background-color: #ffffff;
	border: 1px solid #ff0000;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgqryvaldis span, .zidbgqryvaldis table {
	display: none;
	}
/* objects */
.zidbgobj {	border-collapse: collapse;	border: 2px solid #aa00aa;	}
.zidbgobjkey, .zidbgobjcls {
	color: #000000;
	background-color: #ffccff;
	border: 1px solid #aa00aa;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgobjkeydis {
	color: #555555;
	background-color: #ddccdd;
	border: 1px solid #aa00aa;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgobjval {
	color: #000000;
	background-color: #ffffff;
	border: 1px solid #aa00aa;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
/* strictly numeric arrays */
.zidbgnumarr {	border-collapse: collapse;	border: 2px solid #00aa00;	}
.zidbgnumkey {
	color: #000000;
	background-color: #ccffcc;
	border: 1px solid #00aa00;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgnumkeydis {
	color: #555555;
	background-color: #ccddcc;
	border: 1px solid #00aa00;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgnumval {
	color: #000000;
	background-color: #ffffff;
	border: 1px solid #00aa00;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
/* associative arrays */
.zidbgarr {	border-collapse: collapse;	border: 2px solid #0000ff;	}
.zidbgkey {
	color: #000000;
	background-color: #ccccff;
	border: 1px solid #0000ff;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgkeydis {
	color: #555555;
	background-color: #ccccdd;
	border: 1px solid #0000ff;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
.zidbgval {
	color: #000000;
	background-color: #ffffff;
	border: 1px solid #0000ff;
	padding: 1px;
	vertical-align: top;
	text-align: left;
	}
<?php
		if ($wrap)
		{
?>
</style>
<?php
		}
	}

	// write support JavaScript
	public function writescript($wrap = true)
	{
		$this->writtenscript = true;

		if ($wrap)
		{
?>
<script type="text/javascript">
<?php
		}
?>
function zidbgtgl(obj)
{
	var s = navigator.userAgent.indexOf('Gecko') >= 0 ? 'table-cell' : 'block';
	if (obj.className == 'zidbgkey')
	{
		obj.className = 'zidbgkeydis';
		obj.nextSibling.style.display = 'none';
	}
	else if (obj.className == 'zidbgkeydis')
	{
		obj.className = 'zidbgkey';
		obj.nextSibling.style.display = s;
	}
	else if (obj.className == 'zidbgnumkey')
	{
		obj.className = 'zidbgnumkeydis';
		obj.nextSibling.style.display = 'none';
	}
	else if (obj.className == 'zidbgnumkeydis')
	{
		obj.className = 'zidbgnumkey';
		obj.nextSibling.style.display = s;
	}
	else if (obj.className == 'zidbgobjkey')
	{
		obj.className = 'zidbgobjkeydis';
		obj.nextSibling.style.display = 'none';
	}
	else if (obj.className == 'zidbgobjkeydis')
	{
		obj.className = 'zidbgobjkey';
		obj.nextSibling.style.display = s;
	}
	else if (obj.className == 'zidbgqrykey')
	{
		obj.className = 'zidbgqrykeydis';
		while (obj = obj.nextSibling)
			obj.className = 'zidbgqryvaldis';
	}
	else if (obj.className == 'zidbgqrykeydis')
	{
		obj.className = 'zidbgqrykey';
		var obj2 = obj.parentNode.parentNode.firstChild.firstChild;
		while (obj = obj.nextSibling)
		{
			obj2 = obj2.nextSibling;
			if (obj2.className != 'zidbgqrycoldis')
				obj.className = 'zidbgqryval';
		}
	}
	else if (obj.className == 'zidbgqrycol')
	{
		obj.className = 'zidbgqrycoldis';
		var i = obj.cellIndex;
		obj = obj.parentNode;
		while (obj = obj.nextSibling)
		{
			if (obj.childNodes.length)
				obj.childNodes[i].className = 'zidbgqryvaldis';
		}
	}
	else if (obj.className == 'zidbgqrycoldis')
	{
		obj.className = 'zidbgqrycol';
		var i = obj.cellIndex;
		obj = obj.parentNode;
		while (obj = obj.nextSibling)
		{
			if (obj.childNodes.length)
				if (obj.firstChild.className != 'zidbgqrykeydis')
					obj.childNodes[i].className = 'zidbgqryval';
		}
	}
	else if (obj.className == 'zidbgserkey')
	{
		obj.className = 'zidbgserkeydis';
		obj.nextSibling.style.display = 'none';
	}
	else if (obj.className == 'zidbgserkeydis')
	{
		obj.className = 'zidbgserkey';
		obj.nextSibling.style.display = 'block';
	}
}
<?php
		if ($wrap)
		{
?>
</script>
<?php
		}
	}

	// test whether a particular item should be hidden
	public function is_hidden($key, $parentprefix)
	{
	return 	(array_key_exists($parentprefix . $key, $this->Zi->config['debug']['collapse']) &&
			 $this->Zi->config['debug']['collapse'][$parentprefix . $key]) ||
			(array_key_exists($key, $this->Zi->config['debug']['collapseall']) &&
			 $this->Zi->config['debug']['collapseall'][$key]);
	}

	// dump any variable without requiring a reference
	public function dumpval($var, $hide = false, $parent = '')
	{
		return $this->dump($var, $hide, $parent);
	}

	// dump any variable recursively in a structured way
	public function dump(&$var, $hide = false, $parent = '')
	{
		// write styles and script if they haven't been output yet
		if (!$this->writtencss)
			$this->writecss();
		if (!$this->writtenscript)
			$this->writescript();

		// determine prefix for looking up whether item should be collapsed
		if ($parent == '')
			$parentprefix = '';
		else
			$parentprefix = $parent . '.';

		// see if this is the debug object itself; trying to
		// dump with issue E_NOTICE because the recursion
		// check fails when dumping the debug recursive stack
		if (is_object($var) && $var === $this)
		{
			echo '<table class="zidbgarr"><tr><td class="zidbgkey" title="' . $parent . '">(debug object)</td></tr></table>';
			return;
		}

		// see if this is a recursive reference
		// arrays and objects will be recursively displayed
		// but may contain references to other items, so we
		// track those to avoid infinite recursion
		$unstack = false;

		if (is_array($var))
		{
			if (count($this->_stack) == 0)
			{
				// no object/array stack; create one
				$this->_stack[] = &$var;
			}
			else
			{
				// PHP doesn't offer a way to compare array references,
				// so we fudge it; we set a unique variable in one, and
				// if we find it in any parent-level item we nix the
				// display of this item
				// NOTE: do this before saving the item on the stack
				$var['ZiDumpRecursionCheck01234'] = true;
				for ($i = 0; $i < count($this->_stack); $i++)
					if (is_array($this->_stack[$i]) && array_key_exists('ZiDumpRecursionCheck01234', $this->_stack[$i]))
						break;
				unset($var['ZiDumpRecursionCheck01234']);
				if ($i < count($this->_stack))
				{
					echo '<table class="zidbgarr"><tr><td class="zidbgkey" title="' . $parent . '">(recursive array reference to level ' . $i . ')</td></tr></table>';
					return;
				}

				$this->_stack[] = &$var;
			}
			$unstack = true;
		}
		elseif (is_object($var))
		{
			if (count($this->_stack) == 0)
			{
				// no object/array stack; create one
				$this->_stack[] = $var;			// note this is NOT a reference
			}
			else
			{
				// objects are easier because we can directly compare
				// two object values to see if they refer to the same
				// object
				for ($i = 0; $i < count($this->_stack); $i++)
					if (is_object($this->_stack[$i]) && $this->_stack[$i] === $var)
						break;

				if ($i < count($this->_stack))
				{
					echo '<table class="zidbgarr"><tr><td class="zidbgkey" title="' . $parent . '">(recursive object reference to level ' . $i . ')</td></tr></table>';
					return;
				}

				$this->_stack[] = &$var;
			}
			$unstack = true;
		}

		// scalar variables of various types
		if (is_scalar($var))
		{
			if (is_bool($var))
				echo '<span class="zidbgbool">' . ($var ? 'true' : 'false') . '</span>';
			elseif (is_integer($var))
				echo '<span class="zidbgint">' . $this->Zi->util->safe($var) . '</span>';
			elseif (is_double($var))
				echo '<span class="zidbgdbl">' . $this->Zi->util->safe($var) . '</span>';
			elseif (is_string($var))		// stirng is a special case: might be serialized or JSON
			{
				// try PHP's native serialize format first
				$elevel = error_reporting();
				error_reporting($elevel &~ E_NOTICE);	// suppress E_NOTICE on deserializing errors
				$unserializedvar = unserialize($var);
				error_reporting($elevel);				// restore E_NOTICE setting, if it was on
				if ($unserializedvar !== false || $var === serialize(false))
				{
					// successful deserialization
					echo '<table class="zidbgser"><tr><td class="zidbgserins" colspan="2">';
					$this->dump($unserializedvar, false, $parentprefix.'(serialized)');
					echo "</td></tr>\n";
					echo '<tr><td class="zidbgserkeydis" onclick="zidbgtgl(this);">';
					echo strlen($var) . ' bytes</td><td class="zidbgserins" style="display: none;">';
					echo '<span class="zidbgstr">' . preg_replace('/\n/', '<br />', $this->Zi->util->safe($var)) . '</span>';
					echo '</td></tr></table>';
					return;
				}

				// not that; try JSON next
				if (substr($var, 0, 1) == '{' or substr($var, 0, 1) == '[')
				{
					$unserializedvar = json_decode($var);
					if ($unserializedvar !== null || $var === 'null')
					{
						// successful deserialization
						echo '<table class="zidbgjson"><tr><td class="zidbgjsonins" colspan="2">';
						$this->dump($unserializedvar, false, $parentprefix.'(serialized)');
						echo "</td></tr>\n";
						echo '<tr><td class="zidbgjsonkeydis" onclick="zidbgtgl(this);">';
						echo strlen($var) . ' bytes</td><td class="zidbgjsonins" style="display: none;">';
						echo '<span class="zidbgstr">' . preg_replace('/\n/', '<br />', $this->Zi->util->safe($var)) . '</span>';
						echo '</td></tr></table>';
						return;
					}
				}

				// not that either; just display the string
				echo '<span class="zidbgstr">' . preg_replace('/\n/', '<br />', $this->Zi->util->safe($var)) . '</span>';
			}
			else
				echo '<span class="zidbgint">' . $this->Zi->util->safe($var) . '</span>';
		}

		// special classes of variables
		elseif (is_null($var))
			echo '<span class="zidbgnull">(null)</span>';

		elseif (empty($var))
			echo '<span class="zidbgempty">(empty)</span>';

		// objects
		elseif (is_object($var))
		{
			echo '<table class="zidbgobj"><tr><td colspan="2" class="zidbgobjcls">' . get_class($var) . '</td></tr>' . "\n";
			$baseclass = 'zidbgobj';
			$propcount = 0;
			if ($var instanceof Zirconium_Interface_Dumpable)
			{
				// this class implements Dumpable, which gives
				// us another route to enumerating properties
				$var->dump_rewind();
				while ($var->dump_valid())
				{
					$key = $var->dump_key();
					$value = &$var->dump_current();

					$propcount++;
					if ($hide || $this->is_hidden($key, $parentprefix))
						echo '<tr><td class="' . $baseclass . 'keydis" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val" style="display: none;">';
					else
						echo '<tr><td class="' . $baseclass . 'key" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val">';
					$this->dump($value, false, $parentprefix . $key);
					echo '</td></tr>' . "\n";

					$var->dump_next();
				}
				if ($propcount == 0)
					echo '<tr><td class="zidbgempty">(no properties)</td></tr>';
			}

			elseif ($var instanceof Iterator)
			{
				// this object implements Iterator; we can't
				// use a pass-by-reference iterator, so we
				// can't detect looped objects
				foreach ($var as $key => $value)
				{
					$propcount++;
					if ($hide || $this->is_hidden($key, $parentprefix))
						echo '<tr><td class="' . $baseclass . 'keydis" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val" style="display: none;">';
					else
						echo '<tr><td class="' . $baseclass . 'key" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val">';
					$this->dump($value, false, $parentprefix . $key);
					echo '</td></tr>' . "\n";
				}
				if ($propcount == 0)
					echo '<tr><td class="zidbgempty">(no properties)</td></tr>';
			}

			else
			{
				// ordinary object, iterate over it normally
				// write array values
				foreach ($var as $key => &$value)
				{
					$propcount++;
					if ($hide || $this->is_hidden($key, $parentprefix))
						echo '<tr><td class="' . $baseclass . 'keydis" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val" style="display: none;">';
					else
						echo '<tr><td class="' . $baseclass . 'key" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val">';
					$this->dump($value, false, $parentprefix . $key);
					echo '</td></tr>' . "\n";
				}
				if ($propcount == 0)
					echo '<tr><td class="zidbgempty">(no properties)</td></tr>';
			}
			echo '</table>';
		}

		// resources
		elseif (is_resource($var))
		{
			if (get_resource_type($var) == 'mysql result')
			{
				// mysql results are a known type; display them as recordsets
				$fields = mysql_num_fields($var);
				echo '<table class="zidbgqry"><tr><td class="zidbgqrykey"><div style="width: 100%; height: 100%;" title="MySQL query results">&nbsp;</div></td>';
				for ($i = 0; $i < $fields; $i++)
					echo '<td class="zidbgqrykey">' . $this->Zi->util->safe(mysql_field_name($var, $i)) . '</td>';
				echo "</tr>\n";
				$rows = mysql_num_rows($var);
				if ($rows > 0)
				{
					mysql_data_seek($var, 0);
					for ($j = 0; $j < $rows; $j++)
					{
						echo '<tr><td class="zidbgqrykey">' . $j . '</td>';
						for ($i = 0; $i < $fields; $i++)
						{
							echo '<td class="zidbgqryval">';
							$this->dump(mysql_result($var, $j, $i));
							echo '</td>';
						}
						echo "</tr>\n";
					}
				}
				else
					echo '<tr><td class="zidbgqrykey">empty</td><td colspan="' . $fields . '">This query returned no rows.</td></tr>' . "\n";
				echo '</table>';
			}
			else
				echo '<span class="zidbgrsc">(' . get_resource_type($var) . ')</span>';
		}

		// arrays
		elseif (is_array($var))
		{
			// see if array is two-dimensional (i.e. each entry is an array with numeric ascending keys)
			// we also require that all sub-arrays have the same number of elements
			$is2d = true;
			$k = -1;
			foreach ($var as $key => $value)
			{
				if (is_array($value))
				{
					if ($k < 0)
						$k = count($value);
					else if (count($value) != $k)
						$is2d = false;
					$i = 0;
					foreach ($value as $key2 => &$value2)
						if ($key2 != $i++ || !is_numeric($key2))
						{
							$is2d = false;
							break;
						}
				}
				else
					$is2d = false;
				if (!$is2d)
					break;
			}

			// 2D array; display in column-major order
			// only do this if there are multiple rows, otherwise default to normal array display
			if ($is2d && ($k > 0 || count($var) > 1))
			{
				echo '<table class="zidbgqry"><tr><td class="zidbgqrycol"><div style="width: 100%; height: 100%;" title="2D array">&nbsp;</div></td>';
				foreach ($var as $key => $value)
					echo '<td class="zidbgqrycol" onclick="zidbgtgl(this);">' . $this->Zi->util->safe($key) . '</td>';
				echo "</tr>\n";
				for ($j = 0; $j < $k; $j++)
				{
					echo '<tr><td class="zidbgqrykey" onclick="zidbgtgl(this);">' . $j . '</td>';
					foreach ($var as $key => &$value)
					{
						echo '<td class="zidbgqryval"';
						if (is_numeric($var[$key][$j]) ||
							(is_string($var[$key][$j]) && $var[$key][$j]{0} >= '0' && $var[$key][$j]{0} <= '9'))
						{
							echo ' style="text-align: right !important"';
						}
						echo '>';
						$this->dump($var[$key][$j], false, $parentprefix . $key);
						echo '</td>';
					}
					echo "</tr>\n";
				}
				echo '</table>';
			}

			// not a 2D array; display each item normally
			else
			{
				// see if it's a strictly numeric array
				$isnum = true;
				$i = 0;
				foreach ($var as $key => &$value)
					if ($key != $i++ || !is_numeric($key))
					{
						$isnum = false;
						break;
					}

				// set styles according to array type
				if ($isnum)
				{
					echo '<table class="zidbgnumarr">' . "\n";
					$baseclass = 'zidbgnum';
				}
				else
				{
					echo '<table class="zidbgarr">' . "\n";
					$baseclass = 'zidbg';
				}

				// write array values
				foreach ($var as $key => &$value)
				{
					if ($hide || $this->is_hidden($key, $parentprefix))
						echo '<tr><td class="' . $baseclass . 'keydis" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val" style="display: none;">';
					else
						echo '<tr><td class="' . $baseclass . 'key" onclick="zidbgtgl(this);" title="' . $parent . '">' . $this->Zi->util->safe($key) . '</td><td class="' . $baseclass . 'val">';
					$this->dump($value, false, $parentprefix . $key);
					echo '</td></tr>' . "\n";
				}
				echo '</table>';
			}
		}

		// clean up reference stack
		if ($unstack)
			array_pop($this->_stack);
	}
}

?>