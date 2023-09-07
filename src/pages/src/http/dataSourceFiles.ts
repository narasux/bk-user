import http from './fetch';
import type {
  DataSourceUsersParams,
  DataSourceUsersResult,
  NewDataSourceUserParams,
  PutDataSourceUserParams,
} from './types/dataSourceFiles';

/**
 * 数据源用户信息列表
 */
export const getDataSourceUsers = (params: DataSourceUsersParams): Promise<DataSourceUsersResult> => {
  const { id, username, page, pageSize } = params;
  return http.get(`/api/v1/web/data-sources/${id}/users/?username=${username}&page=${page}&page_size=${pageSize}`);
};

/**
 * 新建数据源用户
 */
export const newDataSourceUser = (params: NewDataSourceUserParams) => http.post(`/api/v1/web/data-sources/${params.id}/users/`, params);

/**
 * 数据源创建用户-下拉部门列表
 */
export const getDataSourceDepartments = (id: string, name: string) => http.get(`/api/v1/web/data-sources/${id}/departments/?name=${name}`);

/**
 * 数据源创建用户-下拉上级列表
 */
export const getDataSourceLeaders = (id: string, keyword: string) => http.get(`/api/v1/web/data-sources/${id}/leaders/?keyword=${keyword}`);

/**
 * 数据源用户详情
 */
export const getDataSourceUserDetails = (id: string) => http.get(`/api/v1/web/data-sources/users/${id}/`);

/**
 * 更新数据源用户
 */
export const putDataSourceUserDetails = (params: PutDataSourceUserParams) => http.put(`/api/v1/web/data-sources/users/${params.id}/`, params);