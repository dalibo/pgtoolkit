%global __ospython3 %{_bindir}/python3
%{expand: %%global py3ver %(echo `%{__ospython3} -c "import sys; sys.stdout.write(sys.version[:3])"`)}
%global python3_sitelib %(%{__ospython3} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")

%global sname pgtoolkit
%global srcname pgtoolkit

Name:		python3-%{sname}
# Must point to a released version on PyPI.
Version:	0.9.1
Release:	1%{?dist}
Epoch:		1
Summary:	Manage Postgres cluster files from Python

License:	PostgreSQL
URL:		https://pypi.org/project/pgtoolkit/
Source0:	https://files.pythonhosted.org/packages/source/%(n=%{srcname}; echo ${n:0:1})/%{srcname}/%{srcname}-%{version}.tar.gz
BuildArch:	noarch
BuildRequires:	python3-setuptools

%description
pgtoolkit provides implementations to manage various file formats in Postgres
cluster or from libpq. Including pg_hba.conf, logs, .pgpass and pg_service.conf.

%prep
%setup -q -n %{srcname}-%{version}

%build
CFLAGS="%{optflags}" %{__ospython3} setup.py build

%install
%{__ospython3} setup.py install --skip-build --root %{buildroot}


%files
%doc README.rst
%{python3_sitelib}/%{sname}-%{version}-py%{py3ver}.egg-info
%dir %{python3_sitelib}/%{sname}
%{python3_sitelib}/%{sname}/*

%changelog
* Tue Jul 28 2020 Denis Laxalde <denis.laxalde@dalibo.com> - 1:0.8.0-1
- Only build the Python3 version.
* Tue Aug 28 2018 Étienne BERSAC <etienne.bersac@dalibo.com> - 1:0.0.1b1-1
- Initial packaging.
