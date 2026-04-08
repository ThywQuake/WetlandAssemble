/Users/mac/.ssh/script/with_pkuhpc_auth.sh rsync -avz --delete --exclude-from=.gitignore ./ 2200013429@wm2-data.pku.edu.cn:/lustre/home/2200013429/repos/WA2/
echo "同步完成于 $(date)"