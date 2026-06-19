clc; 
clear; 
close all;

L = 200; 
t0 = 60;
t1 = 300;
D=1;
M0 = 20;

T = readtable('../input.csv'); 
R = split(T.ExtForceFile, '_'); 
Q = {R{:,2}};
W = {split(Q,'.')};

T.N = cellfun(@str2double,{W{1}{:,:,1}}).';
T.dx = T.N.^(-1)*L;

k = 0;

k = k + 1;
select{k} = 1:4; 
caption{k} = 'Explicit';
x_label{k} = 'dx';
y_label{k} = 'L_1 error';
y_var{k} = 'error_L1';
x_var{k} = 'dx';
x_scale{k} = 'log'; 
y_scale{k} = 'log'; 
graph{k} = 1;
graph_output{k} = 'resolution_influence.png'

k = k + 1;
select{k} = 5:8; 
caption{k} = 'Local timestepping & DtMax=240s';
x_label{k} = 'dx';
y_label{k} = 'L_1 error';
y_var{k} = 'error_L1';
x_var{k} = 'dx';
x_scale{k} = 'log'; 
y_scale{k} = 'log'; 
graph{k} = 1;
graph_output{k} = 'resolution_influence.png'

k = k + 1;
select{k} = 9:12; 
caption{k} = 'Implicit';
x_label{k} = 'dx';
y_label{k} = 'L_1 error';
y_var{k} = 'error_L1';
x_var{k} = 'dx';
x_scale{k} = 'log'; 
y_scale{k} = 'log'; 
graph{k} = 1;
graph_output{k} = 'resolution_influence.png'

% 
k = k + 1;
select{k} = find(T.TransportAutoTimestepdiff==0 & T.N==80); 
caption{k} = 'Explicit';
x_label{k} = 'dtMax';
y_label{k} = 'L_1 error';
y_var{k} = 'error_L1';
x_var{k} = 'dtMax';
x_scale{k} = 'log'; 
y_scale{k} = 'log'; 
graph{k} = 2;
graph_output{k} = 'time_step_influence.png'

k = k + 1;
select{k} = find(T.TransportAutoTimestepdiff==1 & T.N==80); 
caption{k} = 'Local timestepping';
x_label{k} = 'dtMax';
y_label{k} = 'L_1 error';
y_var{k} = 'error_L1';
x_var{k} = 'dtMax';
x_scale{k} = 'log'; 
y_scale{k} = 'log'; 
graph{k} = 2;
graph_output{k} = 'time_step_influence.png'

k = k + 1;
select{k} = find(T.TransportAutoTimestepdiff==3 & T.N==80); 
caption{k} = 'Implicit';
x_label{k} = 'dtMax';
y_label{k} = 'L_1 error';
y_var{k} = 'error_L1';
x_var{k} = 'dtMax';
x_scale{k} = 'log'; 
y_scale{k} = 'log'; 
graph{k} = 2;
graph_output{k} = 'time_step_influence.png'



% determine error
error_L1 = NaN*ones(height(T),1); 
error_Linf = NaN*ones(height(T),1); 
error_L2 = NaN*ones(height(T),1); 
for j = 1:height(T)
    fprintf('Processing row %i\n', j-1)
    output_folder = sprintf('%i', j-1); 
    output_file = fullfile('..', 'output', output_folder, 'dflowfmoutput', 'masscon_map.nc'); 
    gridInfo=EHY_getGridInfo(output_file,'XYcen');
    sed_conc = ncread(output_file, 'mesh2d_tracer');
    x = gridInfo.Xcen;
    f1 = sol(x,t1/D,L,M0,D);
    % figure(1);  
    % hold on; 
    % plot(x,sed_conc(:,end),'o','displayname', 'modelled');
    % plot(x,f1,'-','displayname', 'exact');
    % pause
    % close(1);
    error_L1(j) = mean(abs(reshape(sed_conc(:,end)-f1,[],1)));
    error_Linf(j) = max(abs(reshape(sed_conc(:,end)-f1,[],1)));
    error_L2(j) = mean((reshape(sed_conc(:,end)-f1,[],1)).^2);
end 
T.error_L1 = error_L1;
T.error_Linf = error_Linf; 
T.error_L2 = error_L2; 

for k = 1:length(select) % sim_count 
    fprintf('Processing plot %i\n', k);
    figure(graph{k});
    hold on;
    x=T.(x_var{k});
    x = x(select{k});
    [~, idx] = sort(x); 

    y=T.(y_var{k});
    y=y(select{k});
    plot(x(idx),y(idx), 'DisplayName',caption{k})
end

[figs, ia] = unique(cell2mat(graph))

for f = 1:length(figs); 
    figure(figs(f));
    k = ia(f); 
    xlabel(x_label{k});
    ylabel(y_label{k});
    set(gca, 'XScale', x_scale{k});
    set(gca, 'YScale', y_scale{k});
    grid on;
    box on;
    legend('Location','Best');
    print('-r300','-dpng', graph_output{k});
end


function f = sol(x,t,L,M0,D)
    % https://math.libretexts.org/@go/page/90436 
    % shared under CC BY 3.0 license 
    % (https://creativecommons.org/licenses/by/3.0)
    Nf = 50; 
    a0 = 2*M0/L;
    a = zeros(Nf,1);
    a(4:4:Nf) = 2*M0/L; 
    a(2:4:Nf) = -2*M0/L; 
    
    f = a0/2*ones(size(x));
    for n = 1:Nf
        f = f + a(n)*cos(pi*n*x/L)*exp(-n^2*pi^2*D*t/L^2);
    end
end