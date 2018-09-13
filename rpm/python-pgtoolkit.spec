%if 0%{?fedora} > 23
%{!?with_python3:%global with_python3 1}
%global __ospython3 %{_bindir}/python3
%{expand: %%global py3ver %(echo `%{__ospython3} -c "import sys; sys.stdout.write(sys.version[:3])"`)}
%global python3_sitelib %(%{__ospython3} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
%global __ospython2 %{_bindir}/python2
%{expand: %%global py2ver %(echo `%{__ospython2} -c "import sys; sys.stdout.write(sys.version[:3])"`)}
%global python2_sitelib %(%{__ospython2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
%else
%{!?with_python3:%global with_python3 0}
%global __ospython2 %{_bindir}/python2
%{expand: %%global py2ver %(echo `%{__ospython2} -c "import sys; sys.stdout.write(sys.version[:3])"`)}
%global python2_sitelib %(%{__ospython2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
%endif

%global sname pgtoolkit
%global srcname pgtoolkit

%if 0%{?with_python3}
Name:		python3-%{sname}
%else
Name:		python-%{sname}
%endif
Version:	0.7.0.dev0
Release:	1%{?dist}
Epoch:		1
Summary:	Manage Postgres cluster files from Python

License:	PostgreSQL
URL:		https://pypi.org/project/pgtoolkit/
Source0:	https://files.pythonhosted.org/packages/source/%(n=%{srcname}; echo ${n:0:1})/%{srcname}/%{srcname}-%{version}.tar.gz
BuildArch:	noarch

%description
pgtoolkit provides implementations to manage various file formats in Postgres
cluster or from libpq. Including pg_hba.conf, logs, .pgpass and pg_service.conf.

%prep
%setup -q -n %{srcname}-%{version}

%build
%if 0%{?with_python3}
CFLAGS="%{optflags}" %{__ospython3} setup.py build
%else
CFLAGS="%{optflags}" %{__ospython2} setup.py build
%endif # with_python3

%install
%if 0%{?with_python3}
%{__ospython3} setup.py install --skip-build --root %{buildroot}
%else
%{__ospython2} setup.py install --skip-build --root %{buildroot}
%endif # with_python3


%files
%doc README.rst
%if 0%{?with_python3}
%{python3_sitelib}/%{sname}-%{version}-py%{py3ver}.egg-info
%dir %{python3_sitelib}/%{sname}
%{python3_sitelib}/%{sname}/*
%else
%{python2_sitelib}/%{sname}-%{version}-py%{py2ver}.egg-info
%dir %{python2_sitelib}/%{sname}
%{python2_sitelib}/%{sname}/*
%endif

%changelog
* Tue Aug 28 2018 Étienne BERSAC <etienne.bersac@dalibo.com> - 1:0.0.1b1-1
- Initial packaging.
