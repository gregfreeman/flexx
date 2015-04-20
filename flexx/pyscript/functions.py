import os
from types import FunctionType
import inspect
import subprocess

from .pythonicparser import PythonicParser


def py2js(pycode):
    """ Translate Python code to JavaScript.
    
    parameters:
        pycode (str): the Python code to transalate.
    
    returns:
        jscode (str): the resulting JavaScript.
    """
    parser = PythonicParser(pycode)
    return parser.dump()


def evaljs(jscode, whitespace=True):
    """ Evaluate JavaScript code in Node.js. 
    
    parameters:
        jscode (str): the JavaScript code to evaluate.
        whitespace (bool): if whitespace is False, the whitespace
            is removed from the result.
    
    returns:
        result (str): the last result as a string.
    """
    res = subprocess.check_output(['nodejs', '-p', '-e', jscode])
    res = res.decode().rstrip()
    if res.endswith('undefined'):
        res = res[:-9].rstrip()
    if not whitespace:
        res = res.replace('\n', '').replace('\t', '').replace(' ', '')
    return res


def evalpy(pycode, whitespace=True):
    """ Evaluate PyScript code in Node.js (after translating to JS).
    
    parameters
    ----------
    pycode : str
        the PyScript code to evaluate.
    whitespace : bool
        if whitespace is False, the whitespace is removed from the result.
    
    returns
    -------
    result : str
        the last result as a string.
    """
    # delibirate numpy doc style to see if napoleon handles it the same
    return evaljs(py2js(pycode), whitespace)


def script2js(filename, namespace=None):
    """ Export a .py file to a .js file.
    
    """
    # Import
    assert filename.endswith('.py')
    pycode = open(filename, 'rt').read()
    # Convert
    jscode = PythonicParser(pycode, namespace).dump()
    jscode = '/* Do not edit, autogenerated by flexx.pyscript */\n\n' + jscode
    # Export
    dirname, fname = os.path.split(filename)
    filename2 = os.path.join(dirname, fname[:-3] + '.js')
    open(filename2, 'wt').write(jscode)


def js(ob):
    """ Get the JavaScript code for a class or function. Can be used
    as a decorator.
    
    Parameters:
        func (class, function): The function or class to transtate. If
            this is already JSCode object, it is returned as-is. 
    
    Returns:
        jscode (JSCode): An object that has a ``jscode``, ``pycode`` and
            ``name`` attribute.
    
    Note:
        The Python source code for classes is acquired by name; avoid
        decorating classes in modules where multiple classes with the
        same name are defined. This is a consequence of classes not
        having a corresponding code object (in contrast to functions).
    """
    
    if isinstance(ob, JSCode):
        return ob
    elif isinstance(ob, type):
        thetype = 'class'
    elif isinstance(ob, FunctionType):
        thetype = 'function'
    else:
        raise ValueError('The js decorator only accepts classes '
                         'and real functions.')
    
    # Get name - strip "__js" suffix if it's present
    # This allow mangling the function name on the Python side, to allow
    # the same name for a function in both Py and JS. I investigated
    # other solutions, from class-inside-class constructions to
    # black-magic decorators that auto-mangle the function name. I settled
    # on just allowing "func_name__js".
    name = ob.__name__
    if name.endswith('__js'):
        name = name[:-4]
    
    # Get code
    try:
        lines, linenr = inspect.getsourcelines(ob)
    except Exception as err:
        raise ValueError('Could not get source code for object: %s' % err)
    indent = len(lines[0]) - len(lines[0].lstrip())
    lines = [line[indent:] for line in lines]
    if lines[0].startswith('@'):
        code = ''.join(lines[1:])  # decorated function/class
    else:
        code = ''.join(lines)  # object explicitly passed to js()
    
    return JSCode(thetype, name, code)


class JSCode(object):
    """ Placeholder for storing the original Python code and the JS
    code for a class or function.
    """
    
    def __init__(self, thetype, name, pycode):
        assert thetype in ('function', 'class')
        self._type = thetype
        self._name = name
        self._pycode = pycode
        
        p = PythonicParser(pycode)
        
        if thetype == 'function':
            # Convert to JS, but strip function name, 
            # so that string starts with "function ( ..."
            p._parts[0] = ''  # remove "var xx"
            p._parts[1] = ''  # remove "xx = "
            self._jscode = p.dump()
            assert self._jscode.startswith('function')
        elif thetype == 'class':
            self._jscode = p.dump()
            assert self._jscode.startswith('var %s' % name)
    
    @property
    def type(self):
        """ "function" or "class".
        """
        return self._type
    
    @property
    def name(self):
        """ The name of the class or function.
        """
        return self._name
    
    @property
    def pycode(self):
        """ The Python code that defines this function/class.
        """
        return self._pycode
    
    @property
    def jscode(self):
        """ The resulting JavaScript code for this function/class.
        """
        return self._jscode
    
    def __call__(self, *args, **kwargs):
        action = {'function': 'call', 'class': 'instantiate'}[self._type]
        raise RuntimeError('Cannot %s a JS %s directly from Python' % 
                           (action, self._type))
    
    def __repr__(self):
        
        return '<JSCode %s (print to see code) at 0x%x>' % (self._type, 
                                                            id(self))
    
    def __str__(self):
        pytitle = '== Python code that defines this %s ==' % self._type
        jstitle = '== JS Code that represents this %s ==' % self._type
        return pytitle + '\n' + self.pycode + '\n' + jstitle + self.jscode
